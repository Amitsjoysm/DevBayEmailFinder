import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { verifyApi, resultsApi, jobApi } from '../lib/api';
import { getSocket } from '../lib/socket';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { Progress } from '../components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Slider } from '../components/ui/slider';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Upload, Mail, Play, Pause, Square, Download, CheckCircle, XCircle, AlertTriangle, Loader2, RotateCw, Filter, FileText, HelpCircle, Info, Clock, TrendingUp, ChevronLeft, ChevronRight, History, Eye } from 'lucide-react';
import { toast } from 'sonner';
import Papa from 'papaparse';
import Layout from '../components/Layout';

const Verifier = () => {
  const { user } = useAuth();
  const [singleEmail, setSingleEmail] = useState('');
  const [singleVerifying, setSingleVerifying] = useState(false);
  const [singleResult, setSingleResult] = useState(null);
  
  const [bulkFile, setBulkFile] = useState(null);
  const [threads, setThreads] = useState([10]);
  const [delay, setDelay] = useState([0]);
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [currentJob, setCurrentJob] = useState(null);
  const [jobProgress, setJobProgress] = useState(null);
  const [results, setResults] = useState([]);
  const [jobStatus, setJobStatus] = useState(null);
  const [retrying, setRetrying] = useState(false);
  
  // Filters and pagination
  const [statusFilter, setStatusFilter] = useState('all');
  const [providerFilter, setProviderFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(0);
  const [totalResults, setTotalResults] = useState(0);
  const [pageSize] = useState(50);
  
  // UI states
  const [showInstructions, setShowInstructions] = useState(false);
  const [csvValidationError, setCsvValidationError] = useState(null);
  const [loadingResults, setLoadingResults] = useState(false);
  
  // Job history states
  const [jobHistory, setJobHistory] = useState([]);
  const [showJobHistory, setShowJobHistory] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    const socket = getSocket();
    if (socket) {
      socket.on('job_progress', handleJobProgress);
      socket.on('verification_result', handleVerificationResult);
      socket.on('job_completed', handleJobCompleted);
    }

    return () => {
      if (socket) {
        socket.off('job_progress', handleJobProgress);
        socket.off('verification_result', handleVerificationResult);
        socket.off('job_completed', handleJobCompleted);
      }
    };
  }, []);

  // Load job history on mount
  useEffect(() => {
    loadJobHistory();
  }, []);

  // Poll job status when job is active
  useEffect(() => {
    if (!currentJob || !['queued', 'processing'].includes(jobStatus)) {
      return;
    }

    const pollInterval = setInterval(async () => {
      try {
        const response = await jobApi.get(currentJob);
        const job = response.data;
        setJobStatus(job.status);
        setJobProgress({
          processed: job.processed_records,
          total: job.total_records,
          status: job.status,
          valid_count: job.valid_count,
          invalid_count: job.invalid_count,
          risky_count: job.risky_count
        });

        // Stop polling if job completed
        if (!['queued', 'processing'].includes(job.status)) {
          if (job.status === 'completed') {
            loadResults(currentJob);
            toast.success('Verification completed!');
          }
          setBulkProcessing(false);
        }
      } catch (error) {
        console.error('Failed to poll job status:', error);
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(pollInterval);
  }, [currentJob, jobStatus]);

  const loadJobHistory = async () => {
    setLoadingHistory(true);
    try {
      const response = await jobApi.list();
      // Filter only verification jobs
      const verificationJobs = response.data.filter(job => job.job_type === 'verification');
      setJobHistory(verificationJobs);
    } catch (error) {
      console.error('Failed to load job history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const viewJobResults = async (job) => {
    setCurrentJob(job.id);
    setJobStatus(job.status);
    setJobProgress({
      processed: job.processed_records,
      total: job.total_records,
      status: job.status,
      valid_count: job.valid_count,
      invalid_count: job.invalid_count,
      risky_count: job.risky_count
    });
    
    // Load results for this job
    await loadResults(job.id);
    
    // Scroll to results section
    document.getElementById('results-section')?.scrollIntoView({ behavior: 'smooth' });
    
    toast.success('Loaded job results');
  };

  const handleJobProgress = (data) => {
    setJobProgress(data);
    setJobStatus(data.status);
  };

  const handleVerificationResult = (result) => {
    setResults(prev => [result, ...prev].slice(0, 100));
  };

  const handleJobCompleted = (data) => {
    toast.success('Verification completed!');
    setBulkProcessing(false);
    setJobStatus('completed');
    loadResults(data.job_id);
    loadJobHistory(); // Refresh job history
  };

  const pauseJob = async () => {
    if (!currentJob) return;
    
    try {
      await jobApi.pause(currentJob);
      setJobStatus('paused');
      toast.success('Job paused');
    } catch (error) {
      toast.error('Failed to pause job');
    }
  };

  const resumeJob = async () => {
    if (!currentJob) return;
    
    try {
      await jobApi.resume(currentJob);
      setJobStatus('processing');
      toast.success('Job resumed');
    } catch (error) {
      toast.error('Failed to resume job');
    }
  };

  const stopJob = async () => {
    if (!currentJob) return;
    
    try {
      await jobApi.stop(currentJob);
      setJobStatus('stopped');
      setBulkProcessing(false);
      toast.success('Job stopped');
    } catch (error) {
      toast.error('Failed to stop job');
    }
  };

  const retryFailedVerifications = async () => {
    if (!currentJob) {
      toast.error('No job to retry');
      return;
    }

    setRetrying(true);

    try {
      await jobApi.retry(currentJob);
      toast.success('Retrying failed verifications...');
      
      // Reload results after a delay
      setTimeout(() => {
        loadResults(currentJob);
        setRetrying(false);
      }, 3000);
    } catch (error) {
      toast.error('Failed to retry verifications');
      setRetrying(false);
    }
  };

  const verifySingle = async () => {
    if (!singleEmail) {
      toast.error('Please enter an email');
      return;
    }

    setSingleVerifying(true);
    setSingleResult(null);

    try {
      const response = await verifyApi.single(singleEmail);
      setSingleResult(response.data);
      toast.success('Email verified!');
    } catch (error) {
      toast.error('Verification failed');
    } finally {
      setSingleVerifying(false);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (!file.name.endsWith('.csv')) {
        toast.error('Please upload a CSV file');
        setCsvValidationError('File must be a CSV file');
        return;
      }
      
      // Validate CSV structure
      Papa.parse(file, {
        header: true,
        preview: 5,
        complete: (results) => {
          const headers = results.meta.fields || [];
          const hasEmailColumn = headers.some(h => 
            h.toLowerCase() === 'email' || 
            h.toLowerCase() === 'emails'
          );
          
          if (!hasEmailColumn) {
            toast.error('CSV must contain an "email" column');
            setCsvValidationError('CSV must have an "email" column header');
            setBulkFile(null);
            return;
          }
          
          setCsvValidationError(null);
          setBulkFile(file);
          toast.success(`File "${file.name}" loaded successfully with ${results.data.length}+ rows`);
        },
        error: (error) => {
          toast.error('Failed to parse CSV file');
          setCsvValidationError(error.message);
        }
      });
    }
  };
  
  const downloadSampleCSV = () => {
    const csvContent = 'email\ntest@example.com\nuser@company.com\njohn.doe@organization.org';
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample_verification.csv';
    a.click();
    window.URL.revokeObjectURL(url);
    toast.success('Sample CSV downloaded!');
  };

  const startBulkVerification = async () => {
    if (!bulkFile) {
      toast.error('Please upload a CSV file');
      return;
    }

    setBulkProcessing(true);
    setResults([]);
    setJobStatus('queued');
    setStatusFilter('all');
    setProviderFilter('all');

    try {
      const response = await verifyApi.upload(bulkFile, threads[0], delay[0]);
      setCurrentJob(response.data.job_id);
      toast.success(`Processing ${response.data.total_records} emails`);
      loadJobHistory(); // Refresh job history
    } catch (error) {
      toast.error('Failed to start verification');
      setBulkProcessing(false);
      setJobStatus(null);
    }
  };

  const loadResults = async (jobId, page = 0) => {
    setLoadingResults(true);
    try {
      const status = statusFilter !== 'all' ? statusFilter : null;
      const provider = providerFilter !== 'all' ? providerFilter : null;
      const response = await resultsApi.get(jobId, page * pageSize, pageSize, status, provider);
      setResults(response.data.results);
      setTotalResults(response.data.total);
      setCurrentPage(page);
    } catch (error) {
      console.error('Failed to load results:', error);
      toast.error('Failed to load results');
    } finally {
      setLoadingResults(false);
    }
  };

  // Reload results when filters change
  useEffect(() => {
    if (currentJob) {
      loadResults(currentJob, 0);
    }
  }, [statusFilter, providerFilter]);

  const exportResults = async (format = 'csv') => {
    if (!currentJob) {
      toast.error('No job to export');
      return;
    }

    try {
      const response = await resultsApi.export(currentJob, format);
      
      if (format === 'csv') {
        const blob = new Blob([response.data], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `verification_${currentJob}.csv`;
        a.click();
      } else {
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `verification_${currentJob}.json`;
        a.click();
      }
      
      toast.success('Export successful!');
    } catch (error) {
      toast.error('Export failed');
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      valid: { variant: 'default', className: 'bg-green-600/10 text-green-600 border-green-600/20', icon: CheckCircle },
      invalid: { variant: 'destructive', className: 'bg-red-600/10 text-red-600 border-red-600/20', icon: XCircle },
      risky: { variant: 'secondary', className: 'bg-yellow-600/10 text-yellow-600 border-yellow-600/20', icon: AlertTriangle },
      unknown: { variant: 'secondary', className: 'bg-gray-600/10 text-gray-600 border-gray-600/20', icon: AlertTriangle },
      disposable: { variant: 'destructive', className: 'bg-orange-600/10 text-orange-600 border-orange-600/20', icon: XCircle },
      blocked: { variant: 'destructive', className: 'bg-red-700/10 text-red-700 border-red-700/20', icon: XCircle },
    };

    const config = statusConfig[status] || statusConfig.unknown;
    const Icon = config.icon;

    return (
      <Badge className={`${config.className} border`}>
        <Icon className="w-3 h-3 mr-1" />
        {status}
      </Badge>
    );
  };

  const getJobStatusBadge = (status) => {
    const statusConfig = {
      queued: { className: 'bg-blue-600/10 text-blue-600 border-blue-600/20', label: 'Queued' },
      processing: { className: 'bg-green-600/10 text-green-600 border-green-600/20', label: 'Processing' },
      paused: { className: 'bg-yellow-600/10 text-yellow-600 border-yellow-600/20', label: 'Paused' },
      completed: { className: 'bg-gray-600/10 text-gray-600 border-gray-600/20', label: 'Completed' },
      stopped: { className: 'bg-red-600/10 text-red-600 border-red-600/20', label: 'Stopped' },
      failed: { className: 'bg-red-700/10 text-red-700 border-red-700/20', label: 'Failed' },
    };

    const config = statusConfig[status] || statusConfig.queued;

    return (
      <Badge className={`${config.className} border`}>
        {config.label}
      </Badge>
    );
  };

  const getProviderBadge = (provider) => {
    const colors = {
      Gmail: 'bg-red-600/10 text-red-600',
      GSuite: 'bg-red-600/10 text-red-600',
      Outlook: 'bg-blue-600/10 text-blue-600',
      O365: 'bg-blue-600/10 text-blue-600',
      Yahoo: 'bg-purple-600/10 text-purple-600',
      Zoho: 'bg-yellow-600/10 text-yellow-600',
      Custom: 'bg-gray-600/10 text-gray-600',
    };

    return (
      <Badge className={`${colors[provider] || colors.Custom}`}>
        {provider}
      </Badge>
    );
  };

  const getDeliverabilityScoreBadge = (score) => {
    let className, label, icon;
    
    if (score >= 80) {
      className = 'bg-green-600/10 text-green-600 border-green-600/20';
      label = 'Excellent';
      icon = '🟢';
    } else if (score >= 60) {
      className = 'bg-lime-600/10 text-lime-600 border-lime-600/20';
      label = 'Good';
      icon = '🟡';
    } else if (score >= 40) {
      className = 'bg-yellow-600/10 text-yellow-600 border-yellow-600/20';
      label = 'Fair';
      icon = '🟠';
    } else {
      className = 'bg-red-600/10 text-red-600 border-red-600/20';
      label = 'Poor';
      icon = '🔴';
    }

    return (
      <Badge className={`${className} border font-semibold`} title={`Deliverability Score: ${score}/100 - ${label}`}>
        {icon} {score}
      </Badge>
    );
  };

  return (
    <Layout>
      <div className="space-y-6" data-testid="verifier-container">
        <Card className="bg-surface border border-border/50 p-6">
          <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Single Email Verification</h2>
          <div className="flex gap-4">
            <div className="flex-1">
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" strokeWidth={1.5} />
                <Input
                  data-testid="single-email-input"
                  type="email"
                  value={singleEmail}
                  onChange={(e) => setSingleEmail(e.target.value)}
                  placeholder="email@example.com"
                  className="pl-10 bg-secondary/50 border-border"
                  onKeyPress={(e) => e.key === 'Enter' && verifySingle()}
                />
              </div>
            </div>
            <Button 
              data-testid="verify-single-button"
              onClick={verifySingle} 
              disabled={singleVerifying}
              className="bg-blue-600 hover:bg-blue-700 hover:-translate-y-0.5 transition-transform"
            >
              {singleVerifying ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Verify
            </Button>
          </div>

          {singleResult && (
            <div className="mt-4 p-4 bg-secondary/30 rounded-md border border-border/30" data-testid="single-result">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Status</p>
                  {getStatusBadge(singleResult.status)}
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Provider</p>
                  {getProviderBadge(singleResult.provider)}
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Response Time</p>
                  <p className="text-sm font-medium" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                    {(singleResult.response_time * 1000).toFixed(0)}ms
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Catch-all</p>
                  <p className="text-sm font-medium">
                    {singleResult.is_catch_all ? 'Yes' : 'No'}
                  </p>
                </div>
              </div>
            </div>
          )}
        </Card>

        <Card className="bg-surface border border-border/50 p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h2 className="text-xl font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>Bulk Verification</h2>
              <p className="text-sm text-muted-foreground mt-1">Upload a CSV file with emails to verify in bulk</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowInstructions(!showInstructions)}
              className="hover:bg-secondary/80"
            >
              <HelpCircle className="w-4 h-4 mr-2" />
              {showInstructions ? 'Hide' : 'Show'} Instructions
            </Button>
          </div>
          
          {showInstructions && (
            <div className="mb-6 p-4 bg-blue-600/10 border border-blue-600/20 rounded-md">
              <h3 className="font-bold text-sm mb-2 flex items-center">
                <Info className="w-4 h-4 mr-2 text-blue-600" />
                CSV Format Instructions
              </h3>
              <ul className="text-sm text-muted-foreground space-y-1 ml-6 list-disc">
                <li>CSV file must contain a column named <code className="bg-secondary px-1 py-0.5 rounded">email</code></li>
                <li>One email address per row</li>
                <li>First row should be the header: <code className="bg-secondary px-1 py-0.5 rounded">email</code></li>
                <li>Maximum recommended: 10,000 emails per file</li>
              </ul>
              <div className="mt-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={downloadSampleCSV}
                  className="hover:-translate-y-0.5 transition-transform"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  Download Sample CSV
                </Button>
              </div>
            </div>
          )}
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <Label className="mb-2 block">Upload CSV File</Label>
              <div className="flex gap-2">
                <Input
                  type="file"
                  accept=".csv"
                  onChange={handleFileUpload}
                  data-testid="bulk-file-input"
                  className="bg-secondary/50 border-border"
                />
              </div>
              {bulkFile && !csvValidationError && (
                <p className="text-xs text-green-600 mt-2 flex items-center">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Selected: {bulkFile.name}
                </p>
              )}
              {csvValidationError && (
                <p className="text-xs text-red-600 mt-2 flex items-center">
                  <XCircle className="w-3 h-3 mr-1" />
                  {csvValidationError}
                </p>
              )}
            </div>

            <div className="space-y-4">
              <div>
                <Label className="mb-2 block flex items-center">
                  Threads: {threads[0]}
                  <span className="ml-2 text-xs text-muted-foreground">(Concurrent verifications)</span>
                </Label>
                <Slider
                  data-testid="threads-slider"
                  value={threads}
                  onValueChange={setThreads}
                  min={1}
                  max={100}
                  step={1}
                  className="w-full"
                />
              </div>

              <div>
                <Label className="mb-2 block flex items-center">
                  Delay: {delay[0]}s
                  <span className="ml-2 text-xs text-muted-foreground">(Between requests)</span>
                </Label>
                <Slider
                  data-testid="delay-slider"
                  value={delay}
                  onValueChange={setDelay}
                  min={0}
                  max={30}
                  step={1}
                  className="w-full"
                />
              </div>
            </div>
          </div>

          <div className="flex gap-2 flex-wrap">
            <Button
              data-testid="start-bulk-button"
              onClick={startBulkVerification}
              disabled={bulkProcessing || !bulkFile || csvValidationError}
              className="bg-blue-600 hover:bg-blue-700 hover:-translate-y-0.5 transition-transform"
              title="Start bulk verification process"
            >
              {bulkProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Start Verification
                </>
              )}
            </Button>
            
            {currentJob && jobStatus === 'processing' && (
              <>
                <Button
                  data-testid="pause-job-button"
                  onClick={pauseJob}
                  variant="outline"
                  className="hover:-translate-y-0.5 transition-transform"
                  title="Pause the current job"
                >
                  <Pause className="w-4 h-4 mr-2" />
                  Pause
                </Button>
                <Button
                  data-testid="stop-job-button"
                  onClick={stopJob}
                  variant="destructive"
                  className="hover:-translate-y-0.5 transition-transform"
                  title="Stop the current job permanently"
                >
                  <Square className="w-4 h-4 mr-2" />
                  Stop
                </Button>
              </>
            )}
            
            {currentJob && jobStatus === 'paused' && (
              <Button
                data-testid="resume-job-button"
                onClick={resumeJob}
                className="bg-green-600 hover:bg-green-700 hover:-translate-y-0.5 transition-transform"
                title="Resume the paused job"
              >
                <Play className="w-4 h-4 mr-2" />
                Resume
              </Button>
            )}
            
            {currentJob && (jobStatus === 'completed' || jobStatus === 'stopped') && (
              <Button
                data-testid="retry-button"
                onClick={retryFailedVerifications}
                disabled={retrying}
                variant="outline"
                className="hover:-translate-y-0.5 transition-transform"
                title="Retry all failed and unknown verifications"
              >
                {retrying ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RotateCw className="w-4 h-4 mr-2" />}
                Retry Failed
              </Button>
            )}
            
            {currentJob && (
              <>
                <Button
                  data-testid="export-csv-button"
                  onClick={() => exportResults('csv')}
                  variant="outline"
                  className="hover:-translate-y-0.5 transition-transform"
                  title="Export results as CSV"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export CSV
                </Button>
                <Button
                  data-testid="export-json-button"
                  onClick={() => exportResults('json')}
                  variant="outline"
                  className="hover:-translate-y-0.5 transition-transform"
                  title="Export results as JSON"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export JSON
                </Button>
              </>
            )}
          </div>

          {jobProgress && (
            <div className="mt-6 p-4 bg-secondary/30 rounded-md border border-border/30" data-testid="job-progress">
              <div className="flex justify-between items-center mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Job Status:</span>
                  {getJobStatusBadge(jobStatus)}
                  {jobStatus === 'processing' && (
                    <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                  )}
                </div>
                <div className="text-right">
                  <span className="text-sm font-mono">
                    {jobProgress.processed_records}/{jobProgress.total_records}
                  </span>
                  <p className="text-xs text-muted-foreground">
                    {jobProgress.progress_percentage?.toFixed(1)}% Complete
                  </p>
                </div>
              </div>
              <Progress value={jobProgress.progress_percentage} className="mb-4" />
              
              {/* Live Counter - Current email being processed */}
              {jobStatus === 'processing' && jobProgress.current_email && (
                <div className="mb-4 p-3 bg-indigo-600/10 rounded-md border border-indigo-600/20">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Mail className="w-4 h-4 text-indigo-600 animate-pulse" />
                      <span className="text-sm font-medium text-indigo-600">Currently Checking:</span>
                    </div>
                    <span className="text-sm font-mono text-indigo-600">{jobProgress.current_email}</span>
                  </div>
                  {jobProgress.processing_rate > 0 && (
                    <div className="mt-2 text-xs text-muted-foreground flex items-center justify-end gap-1">
                      <TrendingUp className="w-3 h-3" />
                      Processing at {jobProgress.processing_rate} emails/sec
                    </div>
                  )}
                </div>
              )}
              
              <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-center mb-4">
                <div className="p-3 bg-green-600/10 rounded-md border border-green-600/20">
                  <p className="text-2xl font-bold text-green-600">{jobProgress.valid_count}</p>
                  <p className="text-xs text-muted-foreground">Valid</p>
                </div>
                <div className="p-3 bg-red-600/10 rounded-md border border-red-600/20">
                  <p className="text-2xl font-bold text-red-600">{jobProgress.invalid_count}</p>
                  <p className="text-xs text-muted-foreground">Invalid</p>
                </div>
                <div className="p-3 bg-yellow-600/10 rounded-md border border-yellow-600/20">
                  <p className="text-2xl font-bold text-yellow-600">{jobProgress.risky_count}</p>
                  <p className="text-xs text-muted-foreground">Risky</p>
                </div>
                <div className="p-3 bg-gray-600/10 rounded-md border border-gray-600/20">
                  <p className="text-2xl font-bold text-gray-600">{jobProgress.unknown_count}</p>
                  <p className="text-xs text-muted-foreground">Unknown</p>
                </div>
                <div className="p-3 bg-blue-600/10 rounded-md border border-blue-600/20">
                  <p className="text-2xl font-bold text-blue-600">{jobProgress.active_threads}</p>
                  <p className="text-xs text-muted-foreground">Active Threads</p>
                </div>
                <div className="p-3 bg-purple-600/10 rounded-md border border-purple-600/20">
                  <p className="text-2xl font-bold text-purple-600">
                    {jobProgress.valid_count > 0 ? ((jobProgress.valid_count / jobProgress.processed_records) * 100).toFixed(1) : '0'}%
                  </p>
                  <p className="text-xs text-muted-foreground flex items-center justify-center">
                    <TrendingUp className="w-3 h-3 mr-1" />
                    Success Rate
                  </p>
                </div>
              </div>
              
              {jobProgress.error_count > 0 && (
                <div className="mt-3 p-3 bg-red-600/10 rounded-md border border-red-600/20">
                  <p className="text-sm text-red-600">
                    <AlertTriangle className="w-4 h-4 inline mr-1" />
                    {jobProgress.error_count} errors occurred during processing
                  </p>
                </div>
              )}
              
              {jobProgress.eta_seconds && jobStatus === 'processing' && (
                <div className="mt-3 p-3 bg-blue-600/10 rounded-md border border-blue-600/20">
                  <p className="text-sm text-blue-600 flex items-center justify-center">
                    <Clock className="w-4 h-4 mr-2" />
                    Estimated time remaining: {Math.floor(jobProgress.eta_seconds / 60)}m {jobProgress.eta_seconds % 60}s
                  </p>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Job History Section */}
        <Card className="bg-surface border border-border/50 p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h2 className="text-xl font-bold flex items-center" style={{ fontFamily: 'Chivo, sans-serif' }}>
                <History className="w-5 h-5 mr-2" />
                Previous Jobs
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                View and download results from previous verification jobs
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setShowJobHistory(!showJobHistory);
                if (!showJobHistory) loadJobHistory();
              }}
              className="hover:bg-secondary/80"
            >
              {showJobHistory ? 'Hide' : 'Show'} History
            </Button>
          </div>

          {showJobHistory && (
            <div className="mt-4">
              {loadingHistory ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                  <span className="ml-3 text-muted-foreground">Loading job history...</span>
                </div>
              ) : jobHistory.length > 0 ? (
                <div className="space-y-2">
                  {jobHistory.slice(0, 10).map((job) => (
                    <div 
                      key={job.id} 
                      className={`flex items-center justify-between p-4 bg-secondary/30 rounded-md border transition-all ${
                        currentJob === job.id 
                          ? 'border-blue-600/50 bg-blue-600/5' 
                          : 'border-border/30 hover:border-border/60'
                      }`}
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <p className="text-sm font-mono text-muted-foreground">
                            {job.id.substring(0, 8)}...
                          </p>
                          {getJobStatusBadge(job.status)}
                          <p className="text-xs text-muted-foreground">
                            {new Date(job.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
                          <div>
                            <span className="text-muted-foreground">Records:</span>
                            <span className="ml-1 font-mono">{job.total_records}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Processed:</span>
                            <span className="ml-1 font-mono">{job.processed_records || 0}</span>
                          </div>
                          <div>
                            <span className="text-green-600">Valid:</span>
                            <span className="ml-1 font-mono">{job.valid_count || 0}</span>
                          </div>
                          <div>
                            <span className="text-red-600">Invalid:</span>
                            <span className="ml-1 font-mono">{job.invalid_count || 0}</span>
                          </div>
                          <div>
                            <span className="text-yellow-600">Risky:</span>
                            <span className="ml-1 font-mono">{job.risky_count || 0}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => viewJobResults(job)}
                          className="hover:-translate-y-0.5 transition-transform"
                          title="View results for this job"
                        >
                          <Eye className="w-4 h-4 mr-1" />
                          View Results
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <History className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p>No previous jobs found</p>
                  <p className="text-xs mt-1">Start your first bulk verification above</p>
                </div>
              )}
            </div>
          )}
        </Card>

        {currentJob && (
          <Card className="bg-surface border border-border/50 p-6" id="results-section">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h2 className="text-xl font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>Verification Results</h2>
                <p className="text-xs text-muted-foreground mt-1">
                  Showing {results.length} of {totalResults} results
                </p>
              </div>
              <div className="flex gap-2">
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[150px]" data-testid="status-filter">
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="valid">Valid</SelectItem>
                    <SelectItem value="invalid">Invalid</SelectItem>
                    <SelectItem value="risky">Risky</SelectItem>
                    <SelectItem value="unknown">Unknown</SelectItem>
                    <SelectItem value="disposable">Disposable</SelectItem>
                    <SelectItem value="blocked">Blocked</SelectItem>
                  </SelectContent>
                </Select>
                
                <Select value={providerFilter} onValueChange={setProviderFilter}>
                  <SelectTrigger className="w-[150px]" data-testid="provider-filter">
                    <SelectValue placeholder="Filter by provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Providers</SelectItem>
                    <SelectItem value="Gmail">Gmail</SelectItem>
                    <SelectItem value="GSuite">GSuite</SelectItem>
                    <SelectItem value="Outlook">Outlook</SelectItem>
                    <SelectItem value="O365">O365</SelectItem>
                    <SelectItem value="Yahoo">Yahoo</SelectItem>
                    <SelectItem value="Zoho">Zoho</SelectItem>
                    <SelectItem value="Custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            {loadingResults ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                <span className="ml-3 text-muted-foreground">Loading results...</span>
              </div>
            ) : results.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-border/50">
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Email</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Status</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Score</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Provider</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Response Time</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Retry Count</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Details</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {results.map((result) => (
                        <TableRow key={result.id} className="border-border/50">
                          <TableCell className="font-mono text-sm">{result.email}</TableCell>
                          <TableCell>{getStatusBadge(result.status)}</TableCell>
                          <TableCell>{getDeliverabilityScoreBadge(result.deliverability_score || 0)}</TableCell>
                          <TableCell>{getProviderBadge(result.provider)}</TableCell>
                          <TableCell className="font-mono text-sm">
                            {result.response_time ? (result.response_time * 1000).toFixed(0) : '0'}ms
                          </TableCell>
                          <TableCell>
                            {result.retry_count > 0 ? (
                              <Badge variant="outline" className="bg-orange-600/10 text-orange-600 border-orange-600/20">
                                <RotateCw className="w-3 h-3 mr-1" />
                                {result.retry_count}
                              </Badge>
                            ) : (
                              <span className="text-xs text-muted-foreground">-</span>
                            )}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground max-w-xs">
                            <div className="space-y-1">
                              <div className="truncate" title={result.error_message || result.smtp_response || '-'}>
                                {result.error_message || result.smtp_response || '-'}
                              </div>
                              {result.last_retry_at && (
                                <div className="text-xs text-blue-600 flex items-center">
                                  <Clock className="w-3 h-3 mr-1" />
                                  Last retry: {new Date(result.last_retry_at).toLocaleString()}
                                </div>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                
                {totalResults > pageSize && (
                  <div className="flex items-center justify-between mt-4">
                    <div className="text-sm text-muted-foreground">
                      Page {currentPage + 1} of {Math.ceil(totalResults / pageSize)}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => loadResults(currentJob, currentPage - 1)}
                        disabled={currentPage === 0 || loadingResults}
                      >
                        <ChevronLeft className="w-4 h-4 mr-1" />
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => loadResults(currentJob, currentPage + 1)}
                        disabled={currentPage >= Math.ceil(totalResults / pageSize) - 1 || loadingResults}
                      >
                        Next
                        <ChevronRight className="w-4 h-4 ml-1" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-12">
                <Filter className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No results found</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {statusFilter !== 'all' || providerFilter !== 'all' 
                    ? 'Try adjusting your filters' 
                    : 'Start a verification to see results here'}
                </p>
              </div>
            )}
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Verifier;
