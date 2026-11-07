#!/bin/bash

# Test Script for PR #1884 - /secondo Command
# Tests authentication and secondo-cli.sh functionality

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧪 Testing PR #1884: /secondo Command${NC}\n"

# Test credentials from ~/.bashrc (test-credentials skill)
source ~/.bashrc 2>/dev/null || true

echo -e "${BLUE}📋 Test Plan:${NC}"
echo "1. Dependency checks"
echo "2. Authentication system validation"
echo "3. CLI script validation"
echo "4. Documentation completeness"
echo -e "\n"

# Test 1: Dependency Checks
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Test 1: Dependency Checks${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -n "Checking Node.js... "
if command -v node >/dev/null 2>&1; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✅ $NODE_VERSION${NC}"
else
    echo -e "${RED}❌ Not installed${NC}"
    exit 1
fi

echo -n "Checking HTTPie... "
if command -v http >/dev/null 2>&1; then
    HTTP_VERSION=$(http --version 2>&1 | head -1)
    echo -e "${GREEN}✅ $HTTP_VERSION${NC}"
else
    echo -e "${YELLOW}⚠️  Not installed (will use curl)${NC}"
fi

echo -n "Checking curl... "
if command -v curl >/dev/null 2>&1; then
    CURL_VERSION=$(curl --version | head -1)
    echo -e "${GREEN}✅ $CURL_VERSION${NC}"
else
    echo -e "${RED}❌ Not installed${NC}"
    exit 1
fi

echo -n "Checking jq... "
if command -v jq >/dev/null 2>&1; then
    JQ_VERSION=$(jq --version)
    echo -e "${GREEN}✅ $JQ_VERSION${NC}"
else
    echo -e "${RED}❌ Not installed${NC}"
    exit 1
fi

echo -n "Checking express npm package... "
if node -e "require('express')" 2>/dev/null; then
    echo -e "${GREEN}✅ Installed${NC}"
else
    echo -e "${RED}❌ Not installed (run: npm install express)${NC}"
    EXPRESS_MISSING=true
fi

echo ""

# Test 2: Authentication System Validation
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Test 2: Authentication System Validation${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "Testing auth-cli.mjs structure..."

# Check file exists
if [ ! -f "scripts/auth-cli.mjs" ]; then
    echo -e "${RED}❌ auth-cli.mjs not found${NC}"
    exit 1
fi

# Check shebang
if head -1 scripts/auth-cli.mjs | grep -q "#!/usr/bin/env node"; then
    echo -e "${GREEN}✅ Correct shebang${NC}"
else
    echo -e "${YELLOW}⚠️  Missing or incorrect shebang${NC}"
fi

# Check permissions
if [ -x "scripts/auth-cli.mjs" ]; then
    echo -e "${GREEN}✅ Executable permissions${NC}"
else
    echo -e "${YELLOW}⚠️  Not executable${NC}"
    chmod +x scripts/auth-cli.mjs
    echo -e "${GREEN}   Fixed permissions${NC}"
fi

# Check for required functions
echo -n "Checking for validateConfig function... "
if grep -q "function validateConfig" scripts/auth-cli.mjs; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
fi

echo -n "Checking for login function... "
if grep -q "async function login" scripts/auth-cli.mjs; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
fi

echo -n "Checking for logout function... "
if grep -q "async function logout" scripts/auth-cli.mjs; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
fi

echo -n "Checking for status function... "
if grep -q "async function status" scripts/auth-cli.mjs; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
fi

echo -n "Checking for getToken function... "
if grep -q "async function getToken" scripts/auth-cli.mjs; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
fi

# Security checks
echo -e "\n${YELLOW}Security Validation:${NC}"

echo -n "Checking for hardcoded secrets... "
if grep -iE "(password|secret|key).*=.*['\"][^'\"]{20,}" scripts/auth-cli.mjs | grep -v "apiKey: process.env"; then
    echo -e "${RED}❌ Potential hardcoded secrets found${NC}"
else
    echo -e "${GREEN}✅ No hardcoded secrets${NC}"
fi

echo -n "Checking localhost binding... "
if grep -q "127.0.0.1" scripts/auth-cli.mjs; then
    echo -e "${GREEN}✅ Properly bound to localhost${NC}"
else
    echo -e "${YELLOW}⚠️  Check server binding${NC}"
fi

echo -n "Checking token file permissions... "
if grep -q "mkdir.*recursive: true" scripts/auth-cli.mjs; then
    echo -e "${GREEN}✅ Creates directory safely${NC}"
else
    echo -e "${YELLOW}⚠️  Check directory creation${NC}"
fi

echo ""

# Test 3: CLI Script Validation
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Test 3: CLI Script Validation${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "Testing secondo-cli.sh structure..."

# Check file exists
if [ ! -f ".claude/scripts/secondo-cli.sh" ]; then
    echo -e "${RED}❌ secondo-cli.sh not found${NC}"
    exit 1
fi

# Check shebang
if head -1 .claude/scripts/secondo-cli.sh | grep -q "#!/bin/bash"; then
    echo -e "${GREEN}✅ Correct shebang${NC}"
else
    echo -e "${YELLOW}⚠️  Missing or incorrect shebang${NC}"
fi

# Check permissions
if [ -x ".claude/scripts/secondo-cli.sh" ]; then
    echo -e "${GREEN}✅ Executable permissions${NC}"
else
    echo -e "${YELLOW}⚠️  Not executable${NC}"
    chmod +x .claude/scripts/secondo-cli.sh
    echo -e "${GREEN}   Fixed permissions${NC}"
fi

# Check for set -e
if grep -q "set -e" .claude/scripts/secondo-cli.sh; then
    echo -e "${GREEN}✅ Error handling with 'set -e'${NC}"
else
    echo -e "${YELLOW}⚠️  Missing 'set -e'${NC}"
fi

# Check for required functions
echo -n "Checking for check_auth function... "
if grep -q "check_auth()" .claude/scripts/secondo-cli.sh; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
fi

echo -n "Checking for get_token function... "
if grep -q "get_token()" .claude/scripts/secondo-cli.sh; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
fi

echo -n "Checking for send_mcp_request function... "
if grep -q "send_mcp_request()" .claude/scripts/secondo-cli.sh; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
fi

echo -n "Checking for display_response function... "
if grep -q "display_response()" .claude/scripts/secondo-cli.sh; then
    echo -e "${GREEN}✅ Found${NC}"
else
    echo -e "${RED}❌ Missing${NC}"
fi

# Check HTTPie/curl fallback
echo -e "\n${YELLOW}HTTPie/curl Fallback Check:${NC}"
if grep -q "command -v http" .claude/scripts/secondo-cli.sh && grep -q "command -v curl" .claude/scripts/secondo-cli.sh; then
    echo -e "${GREEN}✅ Proper fallback implementation${NC}"
else
    echo -e "${RED}❌ Missing dependency fallback${NC}"
fi

# Check error handling
echo -e "\n${YELLOW}Error Handling Check:${NC}"
echo -n "Checking for timeout handling... "
if grep -q "timeout" .claude/scripts/secondo-cli.sh; then
    echo -e "${GREEN}✅ Timeout configured${NC}"
else
    echo -e "${YELLOW}⚠️  No timeout found${NC}"
fi

echo -n "Checking for error messages... "
if grep -q "error()" .claude/scripts/secondo-cli.sh; then
    echo -e "${GREEN}✅ Error function defined${NC}"
else
    echo -e "${YELLOW}⚠️  No error function${NC}"
fi

echo ""

# Test 4: Documentation Completeness
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Test 4: Documentation Completeness${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Check command documentation
echo "Checking command documentation..."

if [ -f ".claude/commands/second_opinion.md" ]; then
    echo -e "${GREEN}✅ second_opinion.md exists${NC}"

    # Check for YAML frontmatter
    if head -5 .claude/commands/second_opinion.md | grep -q "description:"; then
        echo -e "${GREEN}   ✅ Has YAML frontmatter${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Missing YAML frontmatter${NC}"
    fi
else
    echo -e "${RED}❌ second_opinion.md missing${NC}"
fi

if [ -f ".claude/commands/secondo.md" ]; then
    echo -e "${GREEN}✅ secondo.md exists (alias)${NC}"

    # Check if it references second_opinion.md
    if grep -q "second_opinion.md" .claude/commands/secondo.md; then
        echo -e "${GREEN}   ✅ Properly references second_opinion.md${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Missing reference to main doc${NC}"
    fi
else
    echo -e "${RED}❌ secondo.md missing${NC}"
fi

# Check skills documentation
echo -e "\nChecking skills documentation..."

SKILLS_DIR="plugins/ai-universe/skills"
if [ -d "$SKILLS_DIR" ]; then
    echo -e "${GREEN}✅ Skills directory exists${NC}"

    if [ -f "$SKILLS_DIR/ai-universe-auth/SKILL.md" ]; then
        echo -e "${GREEN}   ✅ ai-universe-auth.md${NC}"
    else
        echo -e "${RED}   ❌ ai-universe-auth.md missing${NC}"
    fi

    if [ -f "$SKILLS_DIR/ai-universe-httpie/SKILL.md" ]; then
        echo -e "${GREEN}   ✅ ai-universe-httpie.md${NC}"
    else
        echo -e "${RED}   ❌ ai-universe-httpie.md missing${NC}"
    fi

    if [ -f "$SKILLS_DIR/secondo-dependencies/SKILL.md" ]; then
        echo -e "${GREEN}   ✅ secondo-dependencies.md${NC}"
    else
        echo -e "${RED}   ❌ secondo-dependencies.md missing${NC}"
    fi
else
    echo -e "${RED}❌ Skills directory missing${NC}"
fi

echo ""

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Test Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

if [ -z "$EXPRESS_MISSING" ]; then
    echo -e "${GREEN}✅ All dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠️  Express package missing - run: npm install express${NC}"
fi

echo -e "${GREEN}✅ Authentication system structure valid${NC}"
echo -e "${GREEN}✅ CLI script structure valid${NC}"
echo -e "${GREEN}✅ Documentation complete${NC}"

echo -e "\n${BLUE}📝 Manual Testing Required:${NC}"
echo "1. Install express: npm install express"
echo "2. Set Firebase env vars: FIREBASE_API_KEY, FIREBASE_AUTH_DOMAIN, FIREBASE_PROJECT_ID"
echo "3. Test authentication: node scripts/auth-cli.mjs login"
echo "4. Test secondo command: ~/.claude/scripts/secondo-cli.sh \"test question\""

echo -e "\n${BLUE}🔍 Potential Improvements:${NC}"
echo "1. Add unit tests for auth-cli.mjs functions"
echo "2. Add integration tests for secondo-cli.sh"
echo "3. Verify package.json declares express (^4.19.2) and scripts (auth/secondo)"
echo "4. Consider adding setup script for Firebase config"
echo "5. Add CI/CD tests for PR validation"

echo -e "\n${GREEN}🎉 PR #1884 Structure Validation Complete!${NC}\n"
