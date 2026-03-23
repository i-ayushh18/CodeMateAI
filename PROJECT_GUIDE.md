# 📚 CodeMateAI Project Guide

This guide provides comprehensive information about the CodeMateAI project structure, detailed usage examples, and troubleshooting.

## 🏗️ Project Architecture & Structure

```text
CodeMateAI/
├── agents/                    # AI agent implementations with CrewAI orchestration
│   ├── developer_agent.py    # Multi-agent system (reviewer, coder, coordinator)
│   ├── notification_manager.py # Email and webhook notifications
│   ├── tools.py              # CrewAI tools for GitHub operations
│   └── __init__.py
├── integrations/              # External service integrations
│   ├── github_integration.py # GitHub API operations (32KB+ comprehensive)
│   ├── perplexity_integration.py # AI LLM integration
│   └── __init__.py
├── services/                  # Core business logic services
│   ├── pr_processor.py       # PR processing workflows with CrewAI
│   └── __init__.py
├── workspace/                 # Agent working directory for file operations
├── config.py                 # Configuration management with dataclasses
├── config.toml               # TOML configuration file
├── run_agent.py              # Main CLI entry point (687 lines)
└── README.md                 # Quick start guide
```

## 🧠 Core Architecture: CrewAI Multi-Agent System

The project uses a sophisticated **CrewAI-based multi-agent architecture** that orchestrates specialized AI agents:

### **Agent Roles & Responsibilities**

1. **🔍 Reviewer Agent** (`Expert Code Reviewer`)
   - **Role**: Senior code quality analyst
   - **Tools**: `GithubPRReaderTool`
   - **Focus**: Security, performance, maintainability, best practices
   - **Output**: Structured `CodeReviewOutput` with specific actionable changes

2. **💻 Coder Agent** (`Senior Software Engineer`) 
   - **Role**: Feature implementation specialist
   - **Tools**: `GithubFileWriterTool`
   - **Focus**: Translating requirements to production-ready code
   - **Output**: Complete file implementations with full source code

3. **🔄 Coordinator Agent** (`DevOps Coordinator`)
   - **Role**: Workflow and repository manager
   - **Tools**: `GithubPRCreatorTool`, `GithubCommentTool`, `GithubIssueReaderTool`
   - **Focus**: Branch management, PR creation, stakeholder communication
   - **Output**: Successfully integrated changes with proper GitHub workflow

### **CrewAI Tools System**

The agents use specialized tools that abstract GitHub operations:

```python
# Core Tools in agents/tools.py
- GithubPRReaderTool     # Reads PR diffs and file contents
- GithubIssueReaderTool  # Reads issue information
- GithubFileWriterTool   # Creates/updates files on branches
- GithubPRCreatorTool    # Creates pull requests
- GithubCommentTool      # Adds comments to PRs/issues
```

### **Data Flow Architecture**

```
User Input → run_agent.py → Agent Orchestration → GitHub Operations
     ↓              ↓                ↓                    ↓
CLI Args → Config Loading → CrewAI Tasks → Structured Output → GitHub API
     ↓              ↓                ↓                    ↓
Mode Selection → Agent Selection → Tool Usage → Pydantic Models → Repository Changes
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

**What happens behind the scenes:**
1. **🔧 Agent Initialization**: `DeveloperAgent` creates 3 specialized CrewAI agents
2. **📋 Task Creation**: Review task with structured `CodeReviewOutput` Pydantic model
3. **🤖 CrewAI Orchestration**: Sequential task execution with tool usage
4. **📊 Structured Analysis**: AI generates detailed review with specific suggestions
5. **💬 GitHub Integration**: Comments added using `GithubCommentTool`
6. **📝 Notification**: Status updates via `NotificationManager`

#### Developer Mode (Full Processing)
```bash
# Process a specific PR with improvements
python run_agent.py --developer --pr 123

# Process all PRs with improvements
python run_agent.py --developer

# Default mode (developer mode)
python run_agent.py --pr 123
```

**What happens behind the scenes:**
1. **🔧 Multi-Agent Setup**: All 3 CrewAI agents initialized with tools
2. **📋 Review Phase**: Reviewer agent analyzes PR using `GithubPRReaderTool`
3. **💻 Implementation Phase**: Coder agent applies changes via `GithubFileWriterTool`
4. **🔄 Integration Phase**: Coordinator agent creates PR using `GithubPRCreatorTool`
5. **🌿 Branch Management**: Automatic branch creation and management
6. **🔗 Link Creation**: PRs linked back to original with detailed descriptions
7. **📢 Stakeholder Communication**: Comments and notifications sent

### **Issue Processing** ⭐ **CrewAI-Powered Implementation**

#### Complete Issue-to-PR Workflow
```bash
# Implement feature from issue (creates PR!)
python run_agent.py --issue 123 --developer

# Review issue requirements (analyze only)
python run_agent.py --issue 123 --review
```

**Behind the Scenes: CrewAI Multi-Agent Orchestration**

When you run `--issue 123 --developer`, here's the detailed workflow:

```python
# Phase 1: Analysis & Design (Coder Agent)
implementation_task = Task(
    description=f"Analyze issue #{issue_number}: '{issue_title}'. "
               "Use the issue_reader tool for context. "
               "Generate complete, production-ready implementation.",
    agent=self.coder_agent,
    expected_output="Structured feature implementation with multiple files.",
    output_pydantic=FeatureImplementation
)

# Phase 2: DevOps Integration (Coordinator Agent)  
devops_task = Task(
    description=f"Take implementation and apply to branch '{head_branch}'. "
               "Use file_writer tool to save files. "
               "Create detailed Pull Request. "
               "Comment on original issue with PR link.",
    agent=self.coordinator_agent,
    context=[implementation_task],
    expected_output="Success confirmation with PR created and issue updated."
)

# Sequential Execution
implementation_crew = Crew(
    agents=[self.coder_agent, self.coordinator_agent],
    tasks=[implementation_task, devops_task],
    process=Process.sequential,
    verbose=True
)
```

**Detailed Workflow Steps:**
1. **🧠 Issue Analysis**: Coder agent reads issue via `GithubIssueReaderTool`
2. **📐 Architecture Design**: AI plans file structure and implementation approach
3. **� Code Generation**: Production-ready code generated with proper patterns
4. **🌿 Branch Creation**: Feature branch `feature/issue-123-timestamp` created
5. **� File Operations**: Multiple files created via `GithubFileWriterTool`
6. **🔗 PR Creation**: Comprehensive PR with descriptions created via `GithubPRCreatorTool`
7. **💬 Issue Update**: Original issue commented with PR link via `GithubCommentTool`
8. **📊 Structured Output**: `FeatureImplementation` Pydantic model ensures consistency

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

## 🔧 Configuration System

### **Configuration Architecture**

The project uses a sophisticated configuration system with **Python dataclasses** and **TOML files**:

```python
# config.py - Dataclass-based configuration
@dataclass
class GitHubConfig:
    token: str = ""
    repo_owner: str = ""
    repo_name: str = ""
    pr_fetch_limit: int = 10
    include_drafts: bool = False

@dataclass  
class PerplexityConfig:
    api_key: str = ""
    model: str = "sonar-pro"
    temperature: float = 0.7
    max_tokens: int = 2000
```

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

## 🚀 Deep Implementation Details

### **Entry Point: `run_agent.py` (687 lines)**

The main CLI orchestrates the entire system:

```python
# Core initialization flow
async def run_agent(pr_number=None, issue_number=None, repo=None, test_mode=False, 
                   review_mode=False, developer_mode=False, notifications=True, verbose=False):
    
    # 1. Configuration Loading
    config = load_config()
    
    # 2. Integration Initialization  
    github = GitHubIntegration(github_config=config.github)
    llm = PerplexityIntegration(api_key=config.perplexity.api_key, model=config.perplexity.model)
    
    # 3. Agent Setup with CrewAI
    developer_agent = DeveloperAgent(
        llm_integration=llm,
        github_integration=github, 
        notification_manager=notification_manager,
        workspace_dir="./workspace",
        config=config
    )
    
    # 4. Service Initialization
    pr_processor = PRProcessor(config=config, github_integration=github, ...)
    
    # 5. Mode-based Execution
    if issue_number:
        return await process_specific_issue_developer(github, developer_agent, issue_number, notification_manager)
    elif pr_number:
        return await process_specific_pr_developer(github, pr_processor, pr_number, notification_manager)
```

### **CrewAI Integration Details**

#### **Pydantic Models for Structured Output**

```python
class CodeReviewOutput(BaseModel):
    overall_assessment: str = Field(..., description="Overall summary of PR quality")
    is_mergeable: bool = Field(..., description="Whether PR is ready to merge")
    quality_issues: List[str] = Field(default_factory=list, description="Code quality concerns")
    security_concerns: List[str] = Field(default_factory=list, description="Security vulnerabilities")
    performance_issues: List[str] = Field(default_factory=list, description="Performance bottlenecks")
    suggested_changes: List[SuggestedChange] = Field(default_factory=list, description="Actionable improvements")

class FeatureImplementation(BaseModel):
    title: str = Field(..., description="Title of the implementation")
    description: str = Field(..., description="Summary of what was implemented")
    files: List[FileImplementation] = Field(..., description="Files created or updated")
    test_plan: str = Field(..., description="How to verify the implementation")
```

#### **Agent Initialization Process**

```python
# In DeveloperAgent.__init__
self.reviewer_agent = Agent(
    role='Expert Code Reviewer',
    goal='Ensure code quality, security, and maintainability',
    backstory='Veteran software architect with eagle eye for bugs and security holes',
    tools=[self.github_tools["pr_reader"]],
    llm=f"perplexity/{self.llm.model}",
    verbose=True,
    allow_delegation=False
)

self.coder_agent = Agent(
    role='Senior Software Engineer', 
    goal='Implement robust, efficient, and well-tested code features',
    backstory='Brilliant software engineer known for elegant, self-documenting code',
    tools=[self.github_tools["file_writer"]],
    llm=f"perplexity/{self.llm.model}",
    verbose=True,
    allow_delegation=False
)

self.coordinator_agent = Agent(
    role='DevOps Coordinator',
    goal='Manage software development workflow and repository actions', 
    backstory='Ensures proper integration and clear stakeholder communication',
    tools=[self.github_tools["pr_creator"], self.github_tools["comment_tool"], self.github_tools["issue_reader"]],
    llm=f"perplexity/{self.llm.model}",
    verbose=True,
    allow_delegation=False
)
```

### **Service Layer: `PRProcessor`**

The `PRProcessor` service handles the business logic:

```python
class PRProcessor:
    def __init__(self, config: Config, github_integration=None, notification_manager=None, llm_integration=None):
        # Initialize developer agent with all dependencies
        self.developer_agent = DeveloperAgent(
            llm_integration=self.llm_integration,
            github_integration=github_integration,
            notification_manager=notification_manager,
            config=config,
            workspace_dir=getattr(config.agent, 'workspace_dir', './workspace')
        )
    
    async def process_pr(self, pr_info) -> PRProcessingResult:
        # Process PR using CrewAI orchestration
        review_result = await self.developer_agent.review_pr(pr_data)
        
        if review_result.get('success', False):
            # Apply suggested changes if any
            if review_result.get('suggested_changes'):
                # Create new branch and apply changes
                # Create PR with improvements
                pass
```

### **GitHub Integration: 32KB+ Comprehensive API**

The `github_integration.py` provides extensive GitHub operations:

- **Repository Management**: `get_repository()`, `create_branch()`, `delete_branch()`
- **PR Operations**: `get_pull_requests()`, `get_pr_info()`, `create_pull_request()`, `merge_pr()`
- **File Operations**: `get_file_content()`, `update_file()`, `create_file()`
- **Issue Operations**: `get_issues()`, `get_issue_info()`, `create_issue_comment()`
- **Diff Analysis**: `get_pr_diff()`, `get_pr_files()`

### **Error Handling & Resilience**

```python
# Comprehensive error handling in run_agent.py
try:
    # Main execution logic
    result = await process_specific_issue_developer(...)
except Exception as e:
    logger.error(f"Agent failed: {str(e)}", exc_info=True)
    if notification_manager:
        await notification_manager.send_notification(
            message=f"PR Agent failed: {str(e)}",
            level="error"
        )
    return False
finally:
    if llm:
        try:
            await llm.close()
            logger.info("LLM session closed")
        except Exception as close_error:
            logger.warning(f"Error closing LLM session: {close_error}")
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

## 🎉 **What the Agent Can Do: CrewAI-Powered Capabilities**

### **🔄 PR Processing with Multi-Agent Orchestration**
- **🔍 Automated Code Review**: Reviewer agent analyzes PRs using `GithubPRReaderTool`
- **📊 Structured Analysis**: Pydantic-based `CodeReviewOutput` with specific actionable changes
- **🔧 Intelligent Improvements**: Coder agent applies changes via `GithubFileWriterTool`
- **🔄 PR Updates**: Coordinator agent creates improvement PRs via `GithubPRCreatorTool`
- **✅ Merge Operations**: Automated merging when quality thresholds are met

### **💡 Issue Processing: Complete Feature Implementation**
- **📋 Requirement Analysis**: Coder agent reads and understands issues via `GithubIssueReaderTool`
- **🧠 Architecture Design**: AI plans file structure and implementation approach
- **💻 Multi-File Generation**: Production-ready code across multiple files
- **🔄 End-to-End Workflow**: 
  1. Analysis → Design → Implementation → Integration → Communication
  2. Automatic branch creation (`feature/issue-123-timestamp`)
  3. File operations via `GithubFileWriterTool`
  4. PR creation via `GithubPRCreatorTool`
  5. Issue updates via `GithubCommentTool`

### **🛡️ Advanced Code Quality Analysis**
- **Security Scanning**: Identifies vulnerabilities and security anti-patterns
- **Performance Analysis**: Detects bottlenecks and optimization opportunities
- **Style Consistency**: Ensures adherence to best practices and coding standards
- **Documentation Quality**: Analyzes docstrings, comments, and README completeness
- **Test Coverage**: Evaluates test presence and quality

### **🤖 CrewAI Multi-Agent System Benefits**
- **Specialized Expertise**: Each agent has focused role and tools
- **Sequential Processing**: Tasks executed in logical order with context passing
- **Structured Output**: Pydantic models ensure consistent, parseable results
- **Tool Abstraction**: Clean separation between AI logic and GitHub operations
- **Error Resilience**: Comprehensive error handling and recovery mechanisms

### **🌐 Integration & Workflow Automation**
- **🔄 Batch Processing**: Handle multiple PRs/issues with configurable limits
- **📅 Scheduled Operations**: Process items on schedule (via cron/automation)
- **🔔 Smart Notifications**: Email alerts for success/failure states
- **🌍 Multi-Repo Support**: Work across different repositories
- **🐳 Container Deployment**: Full Docker support with volume mounting
- **🔌 Extensible Architecture**: Easy to add new agents, tools, and integrations

## 🔒 Security & Production Considerations

### **API Key Management**
- **🔐 Environment Variables**: Never commit secrets to version control
- **🔄 Key Rotation**: Support for regular API key updates
- **🛡️ Least Privilege**: Minimal required scopes for GitHub tokens
- **📊 Usage Monitoring**: Track API usage and limits

### **Repository Security**
- **🔒 Access Control**: Token-based authentication with proper scopes
- **📋 Audit Trail**: Comprehensive logging of all operations
- **🚫 Safe Operations**: Review-only modes for testing
- **⚡ Rate Limiting**: Respect API rate limits and backoff strategies

### **Production Deployment**
- **🐳 Docker Support**: Full containerization with docker-compose
- **📊 Monitoring**: Structured logging and error tracking
- **🔄 Health Checks**: System status and connectivity validation
- **⚙️ Configuration Management**: TOML-based with environment override support

## 📚 Additional Resources

- **GitHub API Documentation**: https://docs.github.com/en/rest
- **Perplexity AI Documentation**: https://docs.perplexity.ai/
- **Docker Documentation**: https://docs.docker.com/
- **Python asyncio**: https://docs.python.org/3/library/asyncio.html

---

**Need more help?** Check the main [README.md](./README.md) for quick start commands, or open an issue on GitHub for support.
