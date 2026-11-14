package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	transcript "github.com/entireio/cli/transcript"
)

func TestRunConvertsSupportedNativeTranscripts(t *testing.T) {
	tests := []struct {
		name      string
		agent     string
		preserved []string
		noIDs     bool
	}{
		{name: "claude.jsonl", agent: "claude-code", preserved: []string{"2026-10-01T12:00:00.000Z", "msg-001", "Please continue the approved task."}},
		{name: "codex-modern.jsonl", agent: "codex", preserved: []string{"2026-10-01T12:00:01Z", "user-001", "Continue the existing approved work."}},
		{name: "codex-legacy.jsonl", agent: "codex", preserved: []string{"2026-09-01T09:00:01Z", "Resume the already-authorized task."}, noIDs: true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			input, err := os.ReadFile(filepath.Join("testdata", tt.name))
			if err != nil {
				t.Fatal(err)
			}
			var stdout bytes.Buffer
			if err := run([]string{"--agent", tt.agent}, bytes.NewReader(input), &stdout); err != nil {
				t.Fatalf("run failed: %v", err)
			}
			lines, err := transcript.Parse(stdout.Bytes(), transcript.Options{Agent: tt.agent})
			if err != nil {
				t.Fatalf("canonical output did not parse: %v", err)
			}
			if len(lines) == 0 {
				t.Fatal("conversion produced no events")
			}
			var first map[string]json.RawMessage
			if err := json.Unmarshal(bytes.SplitN(stdout.Bytes(), []byte("\n"), 2)[0], &first); err != nil {
				t.Fatal(err)
			}
			if string(first["v"]) != "1" || string(first["agent"]) != `"`+tt.agent+`"` || first["content"] == nil {
				t.Fatalf("output is not canonical Entire v1 JSONL: %s", stdout.String())
			}
			if bytes.Contains(stdout.Bytes(), []byte("V\"")) || bytes.Contains(stdout.Bytes(), []byte("Agent\"")) {
				t.Fatalf("output contains exported Go field casing: %s", stdout.String())
			}
			for _, value := range tt.preserved {
				if !bytes.Contains(stdout.Bytes(), []byte(value)) {
					t.Errorf("canonical output did not preserve %q", value)
				}
			}
			if tt.noIDs && bytes.Contains(stdout.Bytes(), []byte(`"id"`)) {
				t.Fatalf("output fabricated an event ID: %s", stdout.String())
			}
		})
	}
}

func TestRunRejectsMalformedInputWithoutEchoingIt(t *testing.T) {
	secret := `{"text":"private source value"}`
	input := []byte(secret + "\nnot-json\n")
	var stdout bytes.Buffer
	err := run([]string{"--agent", "claude-code"}, bytes.NewReader(input), &stdout)
	if err == nil {
		t.Fatal("malformed input was reported as successful")
	}
	if strings.Contains(err.Error(), secret) || strings.Contains(err.Error(), "private source value") {
		t.Fatalf("error contains source content: %v", err)
	}
	if stdout.Len() != 0 {
		t.Fatalf("partial output was emitted: %q", stdout.String())
	}
}

func TestRunRequiresSupportedAgent(t *testing.T) {
	var stdout bytes.Buffer
	err := run([]string{"--agent", "pi"}, strings.NewReader("{}\n"), &stdout)
	if err == nil {
		t.Fatal("unsupported agent was accepted")
	}
}

func TestVersionJSON(t *testing.T) {
	var stdout bytes.Buffer
	if err := run([]string{"--version"}, strings.NewReader(""), &stdout); err != nil {
		t.Fatal(err)
	}
	var version map[string]string
	if err := json.Unmarshal(stdout.Bytes(), &version); err != nil {
		t.Fatalf("version is not JSON: %v", err)
	}
	if version["sdk"] != "v0.13.4" {
		t.Fatalf("unexpected SDK version: %q", version["sdk"])
	}
}
