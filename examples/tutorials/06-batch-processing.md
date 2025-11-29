# Tutorial 06: Batch Processing

This tutorial covers batch processing capabilities for efficiently testing large patient datasets with the IHE Test Utility.

## Table of Contents

1. [Introduction](#introduction)
2. [Prerequisites](#prerequisites)
3. [Setting Up Batch Configuration](#setting-up-batch-configuration)
4. [Running Batch Processing](#running-batch-processing)
5. [Using Checkpoints for Large Batches](#using-checkpoints-for-large-batches)
6. [Understanding Batch Statistics](#understanding-batch-statistics)
7. [Output Directory Organization](#output-directory-organization)
8. [Performance Tuning](#performance-tuning)
9. [Troubleshooting Common Issues](#troubleshooting-common-issues)

## Introduction

Batch processing allows you to efficiently process large CSV files containing patient data, executing PIX Add and ITI-41 transactions for each patient. Key features include:

- **Checkpoint/Resume**: Resume interrupted batches from where they left off
- **Connection Pooling**: Efficient HTTP connection management for high throughput
- **Per-Operation Logging**: Fine-grained log control for debugging
- **Statistics Tracking**: Throughput, latency, and error rate metrics
- **Organized Output**: Structured directory for logs, documents, and results

## Prerequisites

Before starting this tutorial, ensure you have:

1. Completed [Tutorial 03: PIX Add Workflow](03-pix-add-workflow.md)
2. Completed [Tutorial 04: Complete Workflow](04-complete-workflow.md)
3. A CSV file with patient data (see [examples/patients_sample.csv](../patients_sample.csv))
4. Mock server running or real IHE endpoints configured

## Setting Up Batch Configuration

### Step 1: Choose a Configuration Template

Pre-built configuration templates are available for different environments:

| Template | Use Case |
|----------|----------|
| `config/batch-development.json` | Local development with verbose logging |
| `config/batch-testing.json` | CI/CD testing with moderate logging |
| `config/batch-staging.json` | Pre-production with minimal logging |

### Step 2: Copy and Customize

```bash
# Copy the development template
cp config/batch-development.json config/config.json

# Edit to match your environment
nano config/config.json
```

### Step 3: Key Configuration Options

Here's a complete batch configuration example:

```json
{
  "endpoints": {
    "pix_add_url": "http://localhost:8080/pix/add",
    "iti41_url": "http://localhost:8080/iti41/submit"
  },
  
  "batch": {
    "batch_size": 100,
    "checkpoint_interval": 50,
    "fail_fast": false,
    "concurrent_connections": 10,
    "output_dir": "output/batch-results",
    "resume_enabled": true
  },
  
  "templates": {
    "ccd_template_path": "templates/ccd-template.xml",
    "saml_template_path": "templates/saml-template.xml"
  },
  
  "operation_logging": {
    "csv_log_level": "INFO",
    "pix_add_log_level": "INFO",
    "iti41_log_level": "INFO",
    "saml_log_level": "WARNING"
  },
  
  "logging": {
    "level": "INFO",
    "log_file": "logs/batch.log"
  }
}
```

### Configuration Options Explained

| Option | Description | Recommended Value |
|--------|-------------|-------------------|
| `batch_size` | Maximum patients per batch | 100-500 depending on system |
| `checkpoint_interval` | Save checkpoint every N patients | 50 for development, 100 for production |
| `fail_fast` | Stop on first error | `true` for debugging, `false` for production |
| `concurrent_connections` | HTTP connection pool size | 10-20 for most environments |
| `output_dir` | Where to save results | Unique per batch run |
| `resume_enabled` | Allow resuming interrupted batches | `true` for large batches |

## Running Batch Processing

### Basic Batch Processing

Process all patients in a CSV file:

```bash
ihe-test-util --config config/config.json submit batch examples/patients_sample.csv
```

### With CLI Options

Override configuration with CLI flags:

```bash
ihe-test-util submit batch \
  --config config/config.json \
  --checkpoint-interval 25 \
  --output-dir output/my-batch \
  examples/patients_sample.csv
```

### Fail-Fast Mode

Stop processing on the first error (useful for debugging):

```bash
ihe-test-util submit batch \
  --config config/config.json \
  --fail-fast \
  examples/patients_sample.csv
```

### Sample Output

```
Starting batch processing...
Configuration loaded from: config/config.json
Output directory: output/batch-results

Processing patients from: examples/patients_sample.csv
Total patients: 100
Checkpoint interval: 50 patients

[====================] 100/100 patients (100%)

Batch Processing Complete!
================================
Batch ID: batch-20251128-203000
Duration: 2m 45s
Throughput: 36.4 patients/minute

Results:
  Successful: 97
  Failed: 3
  Error rate: 3.0%

Statistics:
  Avg latency: 1650ms
  PIX Add avg: 650ms
  ITI-41 avg: 1000ms

Output files:
  Results: output/batch-results/results/batch-20251128-203000-results.json
  Summary: output/batch-results/results/batch-20251128-203000-summary.txt
  Audit: output/batch-results/audit/audit-20251128-203000.log
```

## Using Checkpoints for Large Batches

### How Checkpoints Work

1. Checkpoints are automatically saved at the configured interval
2. Each checkpoint records:
   - Last processed patient index
   - Completed patient IDs
   - Failed patient IDs
   - Timestamp

### Automatic Checkpoint Saving

Checkpoints are saved automatically:

```
Processing patients...
[==========          ] 50/100 patients (50%)
Checkpoint saved: output/batch-results/results/checkpoint-batch-20251128-203000.json

[====================] 100/100 patients (100%)
```

### Resuming an Interrupted Batch

If processing is interrupted, resume from the checkpoint:

```bash
# Resume from checkpoint file
ihe-test-util submit batch \
  --config config/config.json \
  --resume output/batch-results/results/checkpoint-batch-20251128-203000.json \
  examples/patients_sample.csv
```

### Resume Output

```
Resuming batch processing...
Loaded checkpoint: batch-20251128-203000
  Last processed index: 50
  Completed: 48 patients
  Failed: 2 patients
  Progress: 50.0%

Continuing from patient 51...
[==========          ] 50/100 resumed
[====================] 100/100 patients (100%)

Batch Processing Complete!
```

### Checkpoint File Structure

```json
{
  "batch_id": "batch-20251128-203000",
  "csv_file_path": "examples/patients_sample.csv",
  "last_processed_index": 50,
  "timestamp": "2025-11-28T20:32:15",
  "completed_patient_ids": ["P001", "P002", "P003", "..."],
  "failed_patient_ids": ["P010", "P025"],
  "total_patients": 100
}
```

## Understanding Batch Statistics

### Statistics Provided

After batch completion, statistics are calculated and reported:

| Metric | Description |
|--------|-------------|
| `throughput_patients_per_minute` | Processing speed |
| `avg_latency_ms` | Average total time per patient |
| `pix_add_avg_latency_ms` | Average PIX Add transaction time |
| `iti41_avg_latency_ms` | Average ITI-41 transaction time |
| `error_rate` | Percentage of failed patients |
| `slowest_patient_id` | Patient that took longest |
| `fastest_patient_id` | Patient that completed fastest |

### Statistics in Results JSON

```json
{
  "batch_id": "batch-20251128-203000",
  "statistics": {
    "total_patients": 100,
    "successful_patients": 97,
    "failed_patients": 3,
    "throughput_patients_per_minute": 36.4,
    "avg_latency_ms": 1650,
    "pix_add_avg_latency_ms": 650,
    "iti41_avg_latency_ms": 1000,
    "error_rate": 0.03,
    "total_processing_time_ms": 165000
  }
}
```

### Performance Targets

For optimal batch processing, aim for these metrics:

| Environment | Throughput | Avg Latency | Error Rate |
|-------------|------------|-------------|------------|
| Development | 10+ pts/min | < 5000ms | < 10% |
| Testing | 20+ pts/min | < 3000ms | < 5% |
| Production | 30+ pts/min | < 2000ms | < 1% |

## Output Directory Organization

### Directory Structure

Batch processing creates an organized directory structure:

```
output/
├── logs/
│   ├── batch-{batch_id}.log      # Main batch log
│   ├── pix-add-{batch_id}.log    # PIX Add transaction log
│   └── iti41-{batch_id}.log      # ITI-41 transaction log
├── documents/
│   └── ccds/
│       ├── patient-P001-ccd.xml  # Generated CCD documents
│       ├── patient-P002-ccd.xml
│       └── ...
├── results/
│   ├── batch-{batch_id}-results.json  # Complete results
│   ├── batch-{batch_id}-summary.txt   # Human-readable summary
│   └── checkpoint-{batch_id}.json     # Latest checkpoint
└── audit/
    └── audit-{batch_id}.log      # Audit trail
```

### Results File

The results JSON contains complete batch information:

```json
{
  "batch_id": "batch-20251128-203000",
  "csv_file_path": "examples/patients_sample.csv",
  "start_timestamp": "2025-11-28T20:30:00",
  "end_timestamp": "2025-11-28T20:32:45",
  "patient_results": [
    {
      "patient_id": "P001",
      "status": "success",
      "pix_add_latency_ms": 650,
      "iti41_latency_ms": 980,
      "total_latency_ms": 1630
    },
    {
      "patient_id": "P002",
      "status": "failed",
      "error_message": "PIX Add failed: Connection timeout"
    }
  ],
  "statistics": { ... }
}
```

### Summary File

Human-readable summary for quick review:

```
Batch Processing Summary
========================
Batch ID: batch-20251128-203000
CSV File: examples/patients_sample.csv
Duration: 2m 45s

Results:
  Total: 100
  Successful: 97 (97.0%)
  Failed: 3 (3.0%)

Performance:
  Throughput: 36.4 patients/minute
  Avg Latency: 1650ms
  PIX Add Avg: 650ms
  ITI-41 Avg: 1000ms

Failed Patients:
  P010: PIX Add failed - Connection timeout
  P025: ITI-41 failed - Document rejected
  P078: PIX Add failed - Duplicate patient ID
```

## Performance Tuning

### Connection Pool Sizing

Adjust `concurrent_connections` based on your environment:

| Environment | Connections | Rationale |
|-------------|-------------|-----------|
| Local dev | 5 | Avoid overwhelming mock server |
| Testing | 10 | Balance between speed and stability |
| Staging | 15-20 | Higher throughput for realistic testing |
| Production | 20-25 | Maximum throughput within limits |

### Checkpoint Interval

Choose interval based on batch size:

| Batch Size | Checkpoint Interval | Rationale |
|------------|---------------------|-----------|
| < 50 | 10 | Frequent saves for small batches |
| 50-200 | 25-50 | Balance between safety and overhead |
| 200-500 | 50-100 | Less frequent for larger batches |
| > 500 | 100 | Minimize checkpoint overhead |

### Logging Optimization

For production batches, reduce logging overhead:

```json
{
  "operation_logging": {
    "csv_log_level": "WARNING",
    "pix_add_log_level": "ERROR",
    "iti41_log_level": "ERROR",
    "saml_log_level": "ERROR"
  }
}
```

### Memory Considerations

For very large batches (1000+ patients):

1. Use streaming CSV processing (default behavior)
2. Set reasonable `batch_size` (500-1000)
3. Enable checkpoints for recovery
4. Monitor system memory usage

## Troubleshooting Common Issues

### Issue: Batch Processing Slow

**Symptoms:**
- Throughput below expected levels
- High latency per patient

**Solutions:**
1. Increase `concurrent_connections`
2. Check network latency to endpoints
3. Reduce logging verbosity
4. Verify mock server capacity

### Issue: Connection Errors

**Symptoms:**
- Frequent "Connection refused" errors
- Timeout errors

**Solutions:**
1. Verify endpoint URLs are correct
2. Check if mock server is running
3. Increase timeout values:
   ```json
   {
     "transport": {
       "timeout_connect": 30,
       "timeout_read": 120
     }
   }
   ```
4. Reduce `concurrent_connections`

### Issue: Checkpoint Not Saving

**Symptoms:**
- No checkpoint file created
- Resume doesn't work

**Solutions:**
1. Verify `output_dir` is writable
2. Check `checkpoint_interval` is less than batch size
3. Ensure `resume_enabled` is `true`

### Issue: High Error Rate

**Symptoms:**
- Many patients failing
- Error rate > 10%

**Solutions:**
1. Enable `fail_fast` to debug first error
2. Increase logging verbosity:
   ```json
   {
     "operation_logging": {
       "pix_add_log_level": "DEBUG",
       "iti41_log_level": "DEBUG"
     }
   }
   ```
3. Check CSV data for validation errors
4. Verify endpoint health

### Issue: Out of Memory

**Symptoms:**
- Process killed
- Memory errors

**Solutions:**
1. Reduce `batch_size`
2. Process in smaller chunks
3. Enable checkpoints for recovery
4. Monitor with `htop` or similar

## Best Practices

1. **Always use checkpoints** for batches > 50 patients
2. **Start with development config** and tune for production
3. **Monitor throughput** to detect performance issues early
4. **Review failed patients** after each batch
5. **Archive results** for audit compliance
6. **Test with small batches** before processing large datasets

## Next Steps

- Review [Configuration Guide](../../docs/configuration-guide.md) for all options
- See [Batch Configuration Templates](../../config/README.md) for environment-specific configs
- Learn about [Mock Server Configuration](../../docs/mock-server-configuration.md)

## Summary

This tutorial covered:

- ✅ Setting up batch configuration
- ✅ Running batch processing with CLI options
- ✅ Using checkpoints for large batches
- ✅ Understanding batch statistics
- ✅ Output directory organization
- ✅ Performance tuning tips
- ✅ Troubleshooting common issues

Batch processing enables efficient testing of large patient datasets with robust error handling and comprehensive reporting.
