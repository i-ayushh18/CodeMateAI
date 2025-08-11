# 📚 CodeMateAI Project Guide

This guide provides comprehensive information about the CodeMateAI project structure, detailed usage examples, and troubleshooting.

## 🏗️ Project Structure

```
CodeMateAI/
├── agents/                    # AI agent implementations
│   ├── developer_agent.py    # Main developer agent (NEW: issue-to-PR functionality)
│   ├── notification_manager.py
│   └── __init__.py
├── integrations/              # External service integrations
│   ├── github_integration.py # GitHub API operations
│   ├── perplexity_integration.py # AI code generation
│   └── __init__.py
├── services/                  # Core business logic
│   ├── pr_processor.py       # PR processing workflows
│   ├── pr_fetcher.py         # PR fetching and management
│   └── __init__.py
├── workspace/                 # Agent working directory
├── config.toml               # Configuration file
├── run_agent.py              # Main entry point

└── README.md                 # Quick start guide
```

## 🎯 Detailed Usage Examples

### **PR Processing Workflows**

#### Review Mode (Analyze Only)
```bash
# Review a specific PR
python run_agent.py --review --pr 123

# Review all open PRs
python run_agent.py --review

# Review with verbose logging
python run_agent.py --verbose --review --pr 123
```

**What happens:**
- Agent fetches PR #123 from GitHub
- Analyzes code using AI (Perplexity)
- Generates review feedback and suggestions
- Adds comments to the PR
- No code changes are made

#### Developer Mode (Full Processing)
```bash
# Process a specific PR with improvements
python run_agent.py --developer --pr 123

# Process all PRs with improvements
python run_agent.py --developer

# Default mode (developer mode)
python run_agent.py --pr 123
```

**What happens:**
- Agent reviews the PR (same as review mode)
- If improvements are suggested, creates a new branch
- Applies the suggested changes
- Creates a new PR with the improvements
- Links back to the original PR

### **Issue Processing** ⭐ **NEW!**

#### Complete Issue-to-PR Workflow
```bash
# Implement feature from issue (creates PR!)
python run_agent.py --issue 123 --developer

# Review issue requirements (analyze only)
python run_agent.py --issue 123 --review
```

**What happens when you run `--issue 123 --developer`:**
1. **📋 Issue Analysis**: Agent reads and analyzes issue #123
2. **🧠 AI Code Generation**: Generates implementation code based on requirements
3. **🌿 Branch Creation**: Creates a new feature branch (`feature/issue-123-timestamp`)
4. **💻 File Creation**: Creates/updates files with the generated code
5. **🔗 PR Creation**: Creates a pull request with the implementation
6. **📝 Issue Linking**: Links the PR back to the original issue
7. **🔔 Notifications**: Sends success/error notifications

**Example Issue → PR Flow:**
```
Issue: "Add user authentication system"
  ↓
Agent generates: auth.py, auth_tests.py, requirements.txt
  ↓
Creates branch: feature/issue-123-1703123456
  ↓
Creates PR: "Implement: Add user authentication system"
  ↓
Links back to original issue with PR URL
```

### **Advanced Usage**

#### Repository-Specific Operations
```bash
# Use a different repository
python run_agent.py --repo owner/repo --review --pr 123
python run_agent.py --repo owner/repo --issue 123 --developer
```

#### Notification Control
```bash
# Disable notifications
python run_agent.py --no-notify --review --pr 123

# Enable notifications (default)
python run_agent.py --notify --developer --pr 123
```

#### Logging and Debugging
```bash
# Enable verbose logging
python run_agent.py --verbose --developer --pr 123

# Quiet mode (minimal output)
python run_agent.py --quiet --review --pr 123
```

## 🧪 Testing and Development

### **Test Scripts**





### **What to Expect During Testing**

- **Review Mode**: Analyzes issue, provides feedback, no changes made
- **Developer Mode**: 
  - Generates code based on issue requirements
  - Creates feature branch
  - Creates pull request
  - Links PR back to original issue
  - Sends notifications

## 🔧 Configuration Details

### **Environment Variables (Recommended)**
```bash
export GITHUB_TOKEN="your_github_token"
export PERPLEXITY_API_KEY="your_perplexity_key"
```

### **Configuration File (`config.toml`)**
```toml
[github]
repo_owner = "your-username"
repo_name = "your-repo"
token = ""  # Set via environment variable
pr_fetch_limit = 5  # Number of PRs to process at once
include_drafts = false  # Whether to process draft PRs

[perplexity]
api_key = ""  # Set via environment variable
model = "sonar-pro"  # LLM model to use

[notifications]
enabled = true
email_to = ["your-email@example.com"]
email_provider = "curl"  # or "smtp"

[agent]
workspace_dir = "./workspace"
max_retries = 3
timeout_seconds = 300
auto_commit = false
target_branch = "main"

[code_review]
enabled = true
rules = ["check_code_style", "check_security", "check_performance"]
```

## 🐳 Docker Commands

### **Build and Run**
```bash
# Build the image
docker build -t pr-agentic-workflow .

# Run the agent
docker run -it --rm \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -v $(pwd)/workspace:/app/workspace \
  -e GITHUB_TOKEN=your_token \
  -e PERPLEXITY_API_KEY=your_key \
  pr-agentic-workflow \
  python run_agent.py --developer --pr 123

# Process issues with Docker
docker run -it --rm \
  -v $(pwd)/config.toml:/app/config.toml:ro \
  -v $(pwd)/workspace:/app/workspace \
  -e GITHUB_TOKEN=your_token \
  -e PERPLEXITY_API_KEY=your_key \
  pr-agentic-workflow \
  python run_agent.py --issue 123 --developer
```

### **Using Docker Compose**
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 🔍 Troubleshooting

### **Common Issues**

#### 1. GitHub Token Issues
```bash
# Check token permissions
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
```

**Symptoms:**
- "GitHub integration not available"
- "Failed to create branch"
- "Failed to create PR"

**Solutions:**
- Ensure token has `repo` scope for private repos
- Check if token is expired
- Verify token has write access to the repository

#### 2. Perplexity API Issues
```bash
# Test API key
curl -H "Authorization: Bearer YOUR_KEY" \
     https://api.perplexity.ai/chat/completions
```

**Symptoms:**
- "Perplexity API key is invalid or expired"
- "Failed to generate code from issue requirements"

**Solutions:**
- Check API key format (should start with `pplx-`)
- Verify API key is valid and not expired
- Check API usage limits

#### 3. Issue Processing Issues
```bash
# Check if issue exists and is accessible
curl -H "Authorization: token YOUR_TOKEN" \
     https://api.github.com/repos/owner/repo/issues/123

# Verify agent has read access to issues
python run_agent.py --issue 123 --review --verbose
```

**Symptoms:**
- "No code blocks found in generated response"
- "Failed to implement feature from issue"

**Solutions:**
- Ensure issue description is detailed enough for AI generation
- Check if issue is accessible to your GitHub token
- Try running in review mode first to see what the AI generates

#### 4. Docker Issues
```bash
# Check container logs
docker-compose logs -f pr-agent

# Rebuild container
docker-compose up -d --build
```

**Symptoms:**
- Container fails to start
- Permission denied errors
- Port conflicts

**Solutions:**
- Ensure Docker is running
- Check port 8000 is available
- Verify file permissions

### **Logs and Debugging**
```bash
# Enable verbose logging
python run_agent.py --verbose --developer --pr 123

# Check log files
tail -f pr_agent.log

# Run with debug information
python run_agent.py --verbose --issue 123 --developer
```

## 🚀 What the Agent Can Do

### **PR Processing**
- 🔍 **Automated Code Review**: AI-powered analysis of pull requests
- 📝 **Smart Comments**: Generate detailed review feedback
- 🔧 **Code Improvements**: Automatically apply suggested changes
- 🔄 **PR Updates**: Update existing PRs with improvements
- ✅ **Merge Operations**: Merge PRs when ready

### **Issue Processing** ⭐ **NEW!**
- 📋 **Read Open Issues**: Automatically reads and understands issue requirements
- 🧠 **Requirement Analysis**: Analyzes issue description, labels, and context
- 💻 **Code Generation**: Generates code based on issue specifications
- 🔄 **Automatic Implementation**: Creates branches, commits changes, creates PRs
- 🔗 **Issue Linking**: Links all changes back to the original issue
- 📧 **Progress Notifications**: Keeps stakeholders informed

**🚀 Full Issue-to-PR Workflow:**
1. **Issue Analysis**: AI reads and understands issue requirements
2. **Code Generation**: Generates production-ready code with proper structure
3. **Branch Management**: Creates feature branches with descriptive names
4. **File Creation**: Creates/updates multiple files as needed
5. **PR Creation**: Automatically creates pull requests with descriptions
6. **Issue Linking**: Comments on original issue with PR link
7. **Error Handling**: Graceful fallbacks and informative error messages

### **Code Quality**
- 🛡️ **Security Scanning**: Identifies potential vulnerabilities
- 📊 **Performance Analysis**: Suggests performance improvements
- 🎨 **Style Consistency**: Ensures code follows best practices
- 📚 **Documentation**: Generates or improves code documentation
- 🧪 **Test Generation**: Creates tests for new functionality

### **Workflow Automation**
- 🔄 **Batch Processing**: Handle multiple PRs/issues simultaneously
- 📅 **Scheduled Reviews**: Process items on a schedule
- 🔔 **Smart Notifications**: Email alerts for important events
- 🌐 **Multi-Repo Support**: Work across different repositories
- 🐳 **Container Ready**: Full Docker support for deployment
- 🤖 **CrewAI Integration**: Compatible with CrewAI for advanced multi-agent orchestration and complex workflows

## 🔒 Security Considerations

### **API Key Management**
- **Never commit secrets to version control!**
- Use environment variables or secure config files
- Rotate API keys regularly
- Use least-privilege access for GitHub tokens

### **Repository Access**
- Limit GitHub token scope to necessary permissions
- Use repository-specific tokens when possible
- Monitor token usage and access logs

## 📚 Additional Resources

- **GitHub API Documentation**: https://docs.github.com/en/rest
- **Perplexity AI Documentation**: https://docs.perplexity.ai/
- **Docker Documentation**: https://docs.docker.com/
- **Python asyncio**: https://docs.python.org/3/library/asyncio.html

---

**Need more help?** Check the main [README.md](./README.md) for quick start commands, or open an issue on GitHub for support.
