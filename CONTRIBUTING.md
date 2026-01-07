# Contributing to ECS Monitoring & AI Recommendations

Thank you for your interest in contributing! 🎉

## 🚀 Quick Start

1. **Fork** the repository
2. **Clone** your fork
3. **Create** a feature branch
4. **Make** your changes
5. **Test** thoroughly
6. **Submit** a pull request

## 📋 Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/aws-ecs-service-recommendations.git
cd aws-ecs-service-recommendations

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Copy environment template
cp .env.example .env
# Edit .env with your settings

# Run application
python app.py
```

## 🎯 How to Contribute

### Reporting Bugs

**Bug Report Template:**
```markdown
**Description**: Brief description

**Steps to Reproduce**:
1. Step 1
2. Step 2

**Expected Behavior**: What should happen

**Actual Behavior**: What actually happens

**Environment**:
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.13]
- Version: [e.g., 1.0.0]
```

### Pull Requests

**PR Checklist:**
- [ ] Code follows project style
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] No merge conflicts

## 💻 Code Style

### Python
- **PEP 8** compliance
- **Type hints** for all functions
- **Docstrings** (Google style)
- **Line length**: 88 characters (Black)

### Commit Messages
```
type(scope): subject

Examples:
feat(api): add rate limiting
fix(auth): resolve JWT expiration
docs(readme): update setup instructions
```

## 📚 Documentation

- Update README.md for user-facing changes
- Add docstrings for all functions
- Include code examples

## 🤝 Community Guidelines

- Be respectful and inclusive
- Follow the Code of Conduct
- Give constructive feedback

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.
