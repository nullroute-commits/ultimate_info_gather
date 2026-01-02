# Report Generation

The framework generates comprehensive reports in multiple formats.

## SystemReport Model

```python
@dataclass
class SystemReport:
    report_id: str
    generated_at: datetime
    generator_version: str
    environment: EnvironmentState | None
    permissions: PermissionsInfo | None
    hardware: HardwareInfo | None
    software: SoftwareInfo | None
    total_collection_time_ms: float
    collection_errors: list[str]
    warnings: list[str]
```

## Output Formats

### JSON Format

Structured data for programmatic use:

```python
report = await orchestrator.collect_all()
outputs = await orchestrator.generate_outputs(report, formats=['json'])

# Or manually:
json_str = report.to_json()
report.save_json(Path('./report.json'))
```

JSON structure:

```json
{
  "report_metadata": {
    "report_id": "uuid-string",
    "generated_at": "2024-01-01T12:00:00",
    "generator_version": "1.0.0",
    "total_collection_time_ms": 1234.56,
    "collection_errors": [],
    "warnings": []
  },
  "environment": {
    "timestamp": "...",
    "python_env": { ... },
    "process_info": { ... },
    ...
  },
  "permissions": { ... },
  "hardware": { ... },
  "software": { ... }
}
```

### Markdown Format

Human-readable documentation:

```python
outputs = await orchestrator.generate_outputs(report, formats=['markdown'])

# Or manually:
md_str = report.get_markdown_report()
report.save_markdown(Path('./report.md'))
```

Features:
- Emoji icons for sections
- Tables for structured data
- Status indicators (✅/❌)
- Proper formatting

### Text Format

Plain text for console/logs:

```python
outputs = await orchestrator.generate_outputs(report, formats=['text'])

# Or manually:
text_str = report.get_full_summary()
```

Features:
- ASCII formatting
- Box drawing characters
- Indented sections
- Summary statistics

## Custom Report Generation

Create custom report formats:

```python
class CustomReportGenerator:
    def __init__(self, report: SystemReport):
        self.report = report
    
    def generate_html(self) -> str:
        """Generate HTML report."""
        html = ["<html><body>"]
        html.append(f"<h1>System Report</h1>")
        html.append(f"<p>Generated: {self.report.generated_at}</p>")
        
        if self.report.environment:
            env = self.report.environment
            html.append("<h2>Environment</h2>")
            html.append(f"<p>Platform: {env.platform_type.name}</p>")
            # ... more content
        
        html.append("</body></html>")
        return "\n".join(html)
    
    def generate_csv(self) -> str:
        """Generate CSV summary."""
        lines = ["Category,Key,Value"]
        
        if self.report.environment:
            env = self.report.environment
            lines.append(f"Environment,Platform,{env.platform_type.name}")
            lines.append(f"Environment,Hostname,{env.hostname}")
            # ... more fields
        
        return "\n".join(lines)
```

## Report Aggregation

Combine multiple reports:

```python
async def collect_from_multiple_hosts(hosts: list[str]):
    """Collect reports from multiple hosts."""
    reports = []
    
    for host in hosts:
        # In real scenario, would run remotely
        orchestrator = InfoGatherOrchestrator()
        report = await orchestrator.collect_all()
        reports.append((host, report))
    
    # Generate combined summary
    summary = {
        "hosts_scanned": len(reports),
        "reports": [
            {
                "host": host,
                "report_id": report.report_id,
                "platform": report.environment.platform_type.name if report.environment else "unknown",
            }
            for host, report in reports
        ]
    }
    
    return summary
```

## Error Handling in Reports

Reports track errors and warnings:

```python
report = await orchestrator.collect_all()

if report.collection_errors:
    print("Collection Errors:")
    for error in report.collection_errors:
        print(f"  - {error}")

if report.warnings:
    print("Warnings:")
    for warning in report.warnings:
        print(f"  - {warning}")

# Check individual sections
if report.hardware is None:
    print("Hardware collection failed completely")
elif report.hardware.errors:
    print("Hardware collection had partial errors")
```
