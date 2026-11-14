package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"

	transcript "github.com/entireio/cli/transcript"
)

const sdkVersion = "v0.13.4"

func main() {
	if err := run(os.Args[1:], os.Stdin, os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, "entire transcript bridge: conversion failed")
		os.Exit(1)
	}
}

func run(args []string, input io.Reader, output io.Writer) error {
	flags := flag.NewFlagSet("entire-transcript-bridge", flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	agent := flags.String("agent", "", "native transcript agent")
	version := flags.Bool("version", false, "print version metadata")
	if err := flags.Parse(args); err != nil || flags.NArg() != 0 {
		return errors.New("invalid arguments")
	}
	if *version {
		return json.NewEncoder(output).Encode(map[string]string{
			"tool": "entire-transcript-bridge",
			"sdk":  sdkVersion,
		})
	}
	if *agent != "codex" && *agent != "claude-code" {
		return errors.New("unsupported agent")
	}
	content, err := io.ReadAll(input)
	if err != nil || len(bytes.TrimSpace(content)) == 0 {
		return errors.New("input unavailable")
	}
	if err := validateJSONLLines(content); err != nil {
		return errors.New("malformed input")
	}
	converted, err := transcript.Convert(content, transcript.Options{Agent: *agent})
	if err != nil {
		return errors.New("conversion failed")
	}
	lines, err := transcript.Parse(converted, transcript.Options{Agent: *agent})
	if err != nil || len(lines) == 0 {
		return errors.New("conversion incomplete")
	}
	if _, err := output.Write(converted); err != nil {
		return errors.New("output unavailable")
	}
	return nil
}

func validateJSONLLines(content []byte) error {
	reader := bufio.NewReader(bytes.NewReader(content))
	seen := false
	for {
		line, err := reader.ReadBytes('\n')
		if err != nil && !errors.Is(err, io.EOF) {
			return err
		}
		trimmed := bytes.TrimSpace(line)
		if len(trimmed) > 0 {
			seen = true
			if !json.Valid(trimmed) {
				return errors.New("invalid JSONL")
			}
		}
		if errors.Is(err, io.EOF) {
			break
		}
	}
	if !seen {
		return errors.New("empty JSONL")
	}
	return nil
}
