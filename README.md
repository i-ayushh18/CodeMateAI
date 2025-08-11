# 🤖 CodeMateAI

An intelligent AI-powered agent that automatically reviews pull requests, suggests improvements, and can even apply code changes and merge PRs.

## 🚀 Quick Start

### 1. **Setup**
```bash
git clone https://github.com/<your-username>/CodeMateAI.git
cd CodeMateAI
cp config.toml.template config.toml
# Edit config.toml with your GitHub token and Perplexity API key
```

### 2. **Install & Run**
```bash
pip install -r requirements.txt
python run_agent.py --help
```

## 🎯 **Essential Commands**

### **PR Processing**
```bash
# Review PR (analyze only)
python run_agent.py --review --pr 123

# Process PR with improvements
python run_agent.py --developer --pr 123

# Process all PRs
python run_agent.py --developer
```

### **Issue Processing** 
```bash
# Implement feature from issue
python run_agent.py --issue 123 --developer

# Review issue (analyze only)
python run_agent.py --issue 123 --review
```

### **Testing & Development**
```bash
# Test mode
python run_agent.py --test

# Verbose logging
python run_agent.py --verbose --developer --pr 123
```

## 🔧 **Configuration**

Set your API keys in `config.toml`:
```toml
[github]
token = "your_github_token"
repo_owner = "your-username"
repo_name = "your-repo"

[perplexity]
api_key = "your_perplexity_key"
```

## 🐳 **Docker (Optional)**

```bash
docker-compose up -d
docker exec pr-agentic-workflow python run_agent.py --help
```

## 📚 **Documentation**

- **Project Structure & Examples**: See [`PROJECT_GUIDE.md`](./PROJECT_GUIDE.md)
- **Deployment Guide**: See [`DEPLOYMENT.md`](./DEPLOYMENT.md)
- **Testing Guide**: See [`TESTING.md`](./TESTING.md)

## 🎉 **What It Does**

- **PR Review**: AI-powered code analysis and suggestions
- **Issue Implementation**: Generate code from issue requirements
- **Auto PR Creation**: Create branches and PRs automatically
- **Code Quality**: Security, performance, and style checks
- **Notifications**: Email alerts for important events

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

**Need help?** Check [`PROJECT_GUIDE.md`](./PROJECT_GUIDE.md) for detailed examples and troubleshooting.
