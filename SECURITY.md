# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### 🔒 Private Disclosure

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please report security issues via:
- **GitHub Security Advisories**: Use the "Security" tab
- **Email**: Create an issue with [SECURITY] prefix

### 📋 What to Include

- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact
- Suggested fix (if any)

### ⏱️ Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**:
  - Critical: 1-7 days
  - High: 7-14 days
  - Medium: 14-30 days

## Security Best Practices

### For Users

1. **Never commit credentials** to version control
2. **Use IAM roles** instead of access keys when possible
3. **Enable encryption** for DynamoDB tables
4. **Rotate credentials** regularly
5. **Use HTTPS** in production

### For Contributors

1. **Never log sensitive data** (credentials, tokens, PII)
2. **Validate all inputs** from users and external sources
3. **Use parameterized queries** for database operations
4. **Follow least privilege principle** for IAM policies

## Known Security Considerations

### AWS Credentials
- Stored in DynamoDB (encrypted at rest recommended)
- Support for multiple authentication methods
- Session tokens expire automatically

### Authentication
- Cognito JWT token validation
- ALB-based OAuth integration
- Optional authentication bypass for local development

### Data Storage
- DynamoDB with TTL for automatic cleanup
- Recommendations expire after 7-30 days
