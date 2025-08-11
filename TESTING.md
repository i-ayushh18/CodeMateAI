# 🧪 CodeMateAI Testing Guide

This guide covers testing the CodeMateAI agent functionality, including the new issue-to-PR features.

## 🚀 Quick Test Commands





## 🎯 What Each Test Does





## 🧪 Testing the Main Agent

### **Basic Functionality Tests**
```bash
# Test help command
python run_agent.py --help

# Test with invalid arguments
python run_agent.py --invalid-flag

# Test configuration loading
python run_agent.py --test
```

### **PR Processing Tests**
```bash
# Test PR review (analyze only)
python run_agent.py --review --pr 123

# Test PR processing with improvements
python run_agent.py --developer --pr 123

# Test with verbose logging
python run_agent.py --verbose --developer --pr 123
```

### **Issue Processing Tests**
```bash
# Test issue review (analyze only)
python run_agent.py --issue 123 --review

# Test issue implementation (creates PR!)
python run_agent.py --issue 123 --developer

# Test with different repositories
python run_agent.py --repo owner/repo --issue 123 --developer
```

## 🔍 Testing Prerequisites

### **Required Setup**
1. **GitHub Token**: Must have repo access and ability to create branches/PRs
2. **Perplexity API Key**: For AI code generation
3. **Issue Access**: Issue must be accessible to your GitHub token
4. **Repository**: Must be configured in `config.toml`

### **Configuration Check**
```bash
# Verify config is loaded correctly
python -c "from config import Config; c = Config(); print('GitHub:', c.github.repo_owner, '/', c.github.repo_name); print('Perplexity:', 'API Key Set' if c.perplexity.api_key else 'No API Key')"
```

## 🐛 Common Testing Issues

### **"Repository information not available"**
- Check `config.toml` GitHub settings
- Verify `repo_owner` and `repo_name` are set

### **"Failed to create branch"**
- Ensure GitHub token has write access
- Check if branch protection rules are enabled

### **"No code blocks found"**
- Issue description may be too vague for AI generation
- Try running in review mode first to see AI output
- Check Perplexity API key and limits

### **"Failed to create PR"**
- Check branch protection rules and permissions
- Verify GitHub token has PR creation rights

## 📊 Testing Results

### **Expected Success Output**
```
✅ Feature implementation successful!
PR URL: https://github.com/owner/repo/pull/456
Branch: feature/issue-123-1703123456
Files created: ['src/main.py', 'tests/test_main.py']
```

### **Expected Error Output**
```
❌ Feature implementation failed: [specific error message]
```

## 🔧 Debug Testing

### **Enable Verbose Logging**
```bash
python run_agent.py --verbose --issue 123 --developer
```

### **Check Logs**
```bash
# View recent logs
tail -f pr_workflow.log

# Check specific log levels
grep "ERROR" pr_workflow.log
grep "INFO" pr_workflow.log
```

### **Test Individual Components**
```bash
# Test GitHub integration
python -c "from integrations.github_integration import GitHubIntegration; from config import Config; g = GitHubIntegration(Config().github); print('GitHub access:', g.get_repository().full_name)"

# Test Perplexity integration
python -c "from integrations.perplexity_integration import PerplexityIntegration; from config import Config; p = PerplexityIntegration(Config().perplexity.api_key); print('Perplexity initialized')"
```

## 🎯 Test Scenarios

### **Scenario 1: Simple Feature Request**
- **Issue**: "Add a hello world function"
- **Expected**: Creates `hello.py` with function, creates PR
- **Test**: `python run_agent.py --issue 123 --developer`

### **Scenario 2: Complex Feature**
- **Issue**: "Implement user authentication system"
- **Expected**: Creates multiple files (auth.py, tests, requirements), creates PR
- **Test**: `python run_agent.py --issue 456 --developer`

### **Scenario 3: Code Review**
- **PR**: Existing pull request with code
- **Expected**: Analyzes code, suggests improvements, optionally applies changes
- **Test**: `python run_agent.py --developer --pr 789`

## 🚨 Testing Best Practices

### **Before Testing**
1. Ensure you have a test repository
2. Create test issues with clear descriptions
3. Have backup of important data
4. Test with small, simple issues first

### **During Testing**
1. Monitor logs for errors
2. Check GitHub for created branches/PRs
3. Verify issue linking works
4. Test both success and failure scenarios

### **After Testing**
1. Clean up test branches if needed
2. Document any issues found
3. Update test cases if needed
4. Share results with team

## 📚 Additional Testing Resources

- **GitHub API Testing**: Use GitHub's API explorer
- **Perplexity API Testing**: Check API documentation for limits
- **Docker Testing**: Test containerized deployment
- **Integration Testing**: Test with real repositories

---

**Need help with testing?** Check the main [PROJECT_GUIDE.md](./PROJECT_GUIDE.md) for detailed examples and troubleshooting.
