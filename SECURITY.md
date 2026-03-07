# Security Policy

## Supported Versions

| Version | Supported          | Notes |
| ------- | ------------------ | ----- |
| 3.0.x   | :white_check_mark: | Current stable, security hardening |
| 2.7.x   | :white_check_mark: | Maintenance mode |
| 2.6.x   | :white_check_mark: | Maintenance mode |
| < 2.6   | :x: | Upgrade recommended |

## Security Features by Version

### v3.0.1 - Security Hardening Release

| Feature | Description | Location |
|---------|-------------|----------|
| **XML Sanitization** | Prevents injection attacks in generated code parsing | `app/tools/code/generate_code.py` |
| **Action Validation** | Only allows `create/modify/delete` actions in generated files | `parse_generated_code()` |
| **Path Traversal Block** | Blocks `..`, absolute paths, `~` in generated file paths | `parse_generated_code()` |
| **Total Byte Limit** | 5MB total limit in `analyze_codebase` prevents memory exhaustion | `app/tools/code/analyze_codebase.py` |
| **Dry-Run Mode** | Preview generated code without writing to disk | `dry_run` parameter |

### v3.0.0 - Major Security Fixes

| Feature | Description | Fix |
|---------|-------------|-----|
| **TOCTOU Race Condition** | File size check after open prevented race attacks | `fstat()` on open file descriptor |
| **Path Traversal in SafeFileWriter** | Backup path could escape sandbox | `is_relative_to()` containment check |
| **DoS Protection** | Unbounded request size | 10MB max request size limit |
| **JSON-RPC Compliance** | Malformed JSON returned wrong error | Proper `-32700` parse error |
| **Plugin Security** | World-writable plugin directories | Permission check before loading |

### v2.6.0+ - Foundation Security

| Feature | Description |
|---------|-------------|
| **Path Sandboxing** | Directory traversal prevention, symlink resolution |
| **Safe File Writing** | Atomic writes, automatic backups, permission preservation |
| **Secrets Sanitization** | Automatic detection and masking of 15+ secret patterns |
| **Input Validation** | Pydantic v2 schemas for type-safe validation |

## API Key Security

### Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables**:
   ```bash
   export GEMINI_API_KEY="your-key-here"
   ```
3. **Use Claude Code's `-e` flag** when registering:
   ```bash
   claude mcp add omni-ai-mcp --scope user \
     -e GEMINI_API_KEY=YOUR_KEY \
     -- python3 ~/.claude-mcp-servers/omni-ai-mcp/run.py
   ```

### What NOT to Do

- Don't paste API keys in `claude_desktop_config.json` if you share configs
- Don't hardcode keys in source files
- Don't commit `.env` files with real keys
- Don't log API keys (use `secrets_sanitizer`)

## Path Sandboxing

All file operations are sandboxed to prevent unauthorized access:

```python
from app.core.security import validate_path, secure_read_file, secure_write_file

# Validates path is within sandbox, blocks traversal attacks
safe_path = validate_path(user_input)

# Secure file operations
content = secure_read_file(file_path)
result = secure_write_file(file_path, content)
```

### Sandbox Configuration

```bash
# Restrict file access to specific directory
export GEMINI_SANDBOX_ROOT=/path/to/project

# Enable/disable sandboxing (default: true)
export GEMINI_SANDBOX_ENABLED=true

# Max file size in bytes (default: 100KB)
export GEMINI_MAX_FILE_SIZE=102400
```

### Protected Operations

- **Directory traversal**: Blocks `../` patterns
- **Symlink resolution**: Follows symlinks and validates destination
- **Absolute path block**: Generated files cannot use `/` or `~` prefixes
- **File size pre-check**: Rejects large files before reading

## Safe File Writing

Atomic writes with automatic backup prevent data loss:

```python
from app.core.security import secure_write_file

result = secure_write_file("/path/to/file.py", "content")
# Backup created at: .gemini_backups/path/to/file.py.TIMESTAMP.bak
```

### Features

- **Atomic writes**: Uses temp file + rename to prevent partial writes
- **Automatic backup**: Timestamped backups (max 5 per file)
- **Permission preservation**: Maintains original file permissions
- **Content verification**: Hash verification after write
- **Auto .gitignore**: Backup directory excluded from git

## Secrets Sanitization

Automatic detection and masking of sensitive data in logs:

```python
from app.core.security import secrets_sanitizer

safe_text = secrets_sanitizer.sanitize("API key: AIzaSyB...")
# Returns: "API key: [REDACTED_GOOGLE_API_KEY]"
```

### Detected Patterns

| Pattern | Example | Masked As |
|---------|---------|-----------|
| Google API Keys | `AIzaSyB...` | `[REDACTED_GOOGLE_API_KEY]` |
| AWS Keys | `AKIA...` | `[REDACTED_AWS_KEY]` |
| GitHub Tokens | `ghp_...`, `gho_...`, `ghs_...`, `ghr_...`, `ghu_...` | `[REDACTED_GITHUB_TOKEN]` |
| JWT Tokens | `eyJ...` | `[REDACTED_JWT]` |
| Bearer Tokens | `Bearer ...` | `[REDACTED_BEARER_TOKEN]` |
| Private Keys | `-----BEGIN...PRIVATE KEY-----` | `[REDACTED_PRIVATE_KEY]` |
| URL Passwords | `://user:pass@` | `[REDACTED_URL_PASSWORD]` |
| Anthropic Keys | `sk-ant-...` | `[REDACTED_ANTHROPIC_KEY]` |
| OpenAI Keys | `sk-...` | `[REDACTED_OPENAI_KEY]` |
| Slack Tokens | `xox...` | `[REDACTED_SLACK_TOKEN]` |

## Input Validation

Pydantic v2 schemas validate all tool inputs:

```python
from app.schemas.inputs import validate_tool_input

# Validates and applies defaults
args = validate_tool_input("ask_gemini", {
    "prompt": "Hello",
    "temperature": 0.9
})

# Raises ValueError for invalid input
validate_tool_input("ask_gemini", {"prompt": "", "temperature": 2.0})
# ValueError: temperature must be <= 1.0
```

### Validated Parameters

- **ask_gemini**: prompt (non-empty), model, temperature (0.0-1.0), thinking_level
- **gemini_generate_code**: prompt, context_files, language, style, dry_run
- **gemini_challenge**: statement, context, focus
- **gemini_analyze_codebase**: prompt, files, analysis_type
- **gemini_code_review**: code, focus, model
- **gemini_brainstorm**: topic, methodology, idea_count

## Code Generation Security

### XML Sanitization (v3.0.1)

LLM output is sanitized before parsing to prevent injection:

```python
from app.tools.code.generate_code import sanitize_xml_content, parse_generated_code

# Always sanitize LLM output before parsing
clean_xml = sanitize_xml_content(raw_llm_output)
files = parse_generated_code(clean_xml)
```

### Sanitization Steps

1. **Control character removal**: Strips `\x00-\x08`, `\x0b`, `\x0c`, `\x0e-\x1f`, `\x7f`
2. **Excessive newline normalization**: Reduces 4+ consecutive newlines to 3
3. **Action validation**: Only `create`, `modify`, `delete` actions allowed
4. **Path traversal block**: Rejects paths containing `..`, starting with `/` or `~`

### Dry-Run Mode

Preview generated code without writing to disk:

```python
# With dry_run=True, no files are written
result = tool_generate_code(
    prompt="Create a config module",
    output_dir="src/",
    dry_run=True  # Preview only
)
# Returns preview showing what would be created
```

## Data Privacy

### What Data is Sent to Google

When using this MCP server, the following data is sent to Google's Gemini API:

- **Text prompts** for ask_gemini, code_review, brainstorm, challenge, web_search
- **Code snippets** for code_review, analyze_codebase, generate_code
- **Documents** uploaded to File Search stores
- **Images** for gemini_analyze_image (vision analysis)
- **Image/Video prompts** for generation tools
- **Text** for text-to-speech conversion

### Data Retention

- Refer to [Google AI's privacy policy](https://ai.google.dev/gemini-api/terms)
- File Search stores persist on Google's servers until deleted
- Generated images/videos are temporarily stored during generation
- Conversation history stored locally in SQLite (`~/.omni-ai-mcp/conversations.db`)

### Sensitive Data Guidelines

**Do not send:**
- Passwords or credentials
- Private keys or tokens
- Personal identifiable information (PII)
- Confidential business data
- Healthcare/financial data subject to regulations

## Docker Security (v2.7.0+)

Production container with security hardening:

```yaml
# docker-compose.yml security features
security_opt:
  - no-new-privileges:true    # Prevent privilege escalation
read_only: true               # Read-only root filesystem
user: "1000:1000"             # Non-root user
```

### Docker Features

- **Non-root user**: Runs as `gemini` user (UID 1000)
- **Read-only filesystem**: Root filesystem is read-only
- **No new privileges**: Prevents privilege escalation
- **Resource limits**: CPU and memory limits prevent resource exhaustion
- **Tmpfs for temp**: Temp directory uses tmpfs, not persistent storage
- **Health checks**: Container health monitored every 30 seconds

## Reporting Vulnerabilities

### How to Report

1. **Do NOT** open a public issue for security vulnerabilities
2. Email the maintainer directly (see repository owner profile)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

| Phase | Timeline |
|-------|----------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 1 week |
| Fix timeline | Depends on severity |

### Severity Levels

| Level | Description | Response |
|-------|-------------|----------|
| Critical | API key exposure, RCE, sandbox escape | Immediate fix, emergency release |
| High | Data leakage, auth bypass, path traversal | Fix within 1 week |
| Medium | Logic errors, DoS, information disclosure | Fix within 1 month |
| Low | Minor issues, hardening improvements | Next release |

## Security Checklist for Contributors

When adding new tools or modifying existing ones:

- [ ] Use `validate_path()` for any file path input
- [ ] Use `secure_read_file()` / `secure_write_file()` for file operations
- [ ] Never expose raw exception details to users
- [ ] Respect `SANDBOX_ROOT` boundaries
- [ ] Sanitize any logged data with `secrets_sanitizer`
- [ ] Sanitize LLM output before parsing (especially XML)
- [ ] Add Pydantic schema for input validation
- [ ] Test with malicious inputs (path traversal, injection)

## Known Limitations

1. **No encryption at rest**: Files uploaded to RAG stores are stored on Google's servers
2. **No access control**: Anyone with access to Claude Code can use the MCP tools
3. **API key visibility**: The key is visible to processes that can read environment variables
4. **Local SQLite**: Conversation history stored in plaintext SQLite database

## Security Updates

Watch the repository for security-related releases. Update promptly when security patches are released:

```bash
git pull origin main
./setup.sh YOUR_API_KEY
# Restart Claude Code
```

---

Last updated: v3.0.1 (2025-12-08)
