import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { finderApi, resultsApi, jobApi } from '../lib/api';
import { getSocket } from '../lib/socket';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Slider } from '../components/ui/slider';
import { Search, Upload, CheckCircle, XCircle, Clock, Loader2, Download, Play, Pause, Square, AlertTriangle, FileText, HelpCircle, Info, TrendingUp, ChevronLeft, ChevronRight, Filter, History, Eye } from 'lucide-react';
import { toast } from 'sonner';
import Papa from 'papaparse';
import Layout from '../components/Layout';

const Finder = () => {
  const { user } = useAuth();
  
  // Single finder state
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [domain, setDomain] = useState('');
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);

  // Bulk finder state
  const [bulkFile, setBulkFile] = useState(null);
  const [threads, setThreads] = useState([10]);
  const [bulkProcessing, setBulkProcessing] = useState(false);
  const [currentJob, setCurrentJob] = useState(null);
  const [jobProgress, setJobProgress] = useState(null);
  const [finderResults, setFinderResults] = useState([]);
  const [jobStatus, setJobStatus] = useState(null);
  
  // UI states
  const [showInstructions, setShowInstructions] = useState(false);
  const [csvValidationError, setCsvValidationError] = useState(null);
  const [loadingResults, setLoadingResults] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const [totalResults, setTotalResults] = useState(0);
  const [pageSize] = useState(50);
  
  // Job history states
  const [jobHistory, setJobHistory] = useState([]);
  const [showJobHistory, setShowJobHistory] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    const socket = getSocket();
    if (socket) {
      socket.on('job_progress', handleJobProgress);
      socket.on('finder_result', handleFinderResult);
      socket.on('job_completed', handleJobCompleted);
    }

    return () => {
      if (socket) {
        socket.off('job_progress', handleJobProgress);
        socket.off('finder_result', handleFinderResult);
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
          found_count: job.valid_count || 0,
          not_found_count: job.invalid_count || 0
        });

        // Stop polling if job completed
        if (!['queued', 'processing'].includes(job.status)) {
          if (job.status === 'completed') {
            loadFinderResults(currentJob, 0);
            toast.success('Email finding completed!');
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
      // Filter only finder jobs
      const finderJobs = response.data.filter(job => job.job_type === 'finder');
      setJobHistory(finderJobs);
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
      found_count: job.valid_count || 0,
      not_found_count: job.invalid_count || 0
    });
    
    // Load results for this job
    await loadFinderResults(job.id, 0);
    
    // Scroll to results section
    document.getElementById('results-section')?.scrollIntoView({ behavior: 'smooth' });
    
    toast.success('Loaded job results');
  };

  const handleJobProgress = (data) => {
    if (data.job_id === currentJob) {
      setJobProgress(data);
      setJobStatus(data.status);
    }
  };

  const handleFinderResult = (result) => {
    setFinderResults(prev => [result, ...prev].slice(0, 100));
  };

  const handleJobCompleted = (data) => {
    if (data.job_type === 'finder' && data.job_id === currentJob) {
      toast.success('Email finding completed!');
      setBulkProcessing(false);
      setJobStatus('completed');
      loadFinderResults(data.job_id, 0);
      loadJobHistory(); // Refresh job history
    }
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

  const findEmail = async () => {
    if (!firstName || !lastName || !domain) {
      toast.error('Please fill all fields');
      return;
    }

    setSearching(true);
    setResult(null);

    try {
      const response = await finderApi.single({
        first_name: firstName,
        last_name: lastName,
        domain: domain
      });
      setResult(response.data);
      if (response.data.found) {
        toast.success(`Found: ${response.data.email}`);
      } else {
        toast.error('No valid email found');
      }
    } catch (error) {
      toast.error('Search failed');
      console.error(error);
    } finally {
      setSearching(false);
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
          const hasFirstName = headers.some(h => 
            h.toLowerCase().includes('first') && h.toLowerCase().includes('name')
          );
          const hasLastName = headers.some(h => 
            h.toLowerCase().includes('last') && h.toLowerCase().includes('name')
          );
          const hasDomain = headers.some(h => 
            h.toLowerCase() === 'domain' || h.toLowerCase().includes('company')
          );
          
          if (!hasFirstName || !hasLastName || !hasDomain) {
            toast.error('CSV must contain first_name, last_name, and domain columns');
            setCsvValidationError('CSV must have first_name, last_name, and domain columns');
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
    const csvContent = 'first_name,last_name,domain\nJohn,Doe,example.com\nJane,Smith,company.com\nMike,Johnson,organization.org';
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample_finder.csv';
    a.click();
    window.URL.revokeObjectURL(url);
    toast.success('Sample CSV downloaded!');
  };

  const startBulkFinder = async () => {
    if (!bulkFile) {
      toast.error('Please upload a CSV file');
      return;
    }

    setBulkProcessing(true);
    setFinderResults([]);
    setJobProgress(null);
    setJobStatus('queued');

    try {
      const response = await finderApi.upload(bulkFile, threads[0]);
      setCurrentJob(response.data.job_id);
      toast.success(`Finding emails for ${response.data.total_records} records`);
      loadJobHistory(); // Refresh job history
    } catch (error) {
      toast.error('Failed to start bulk finder');
      console.error(error);
      setBulkProcessing(false);
      setJobStatus(null);
    }
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

  const loadFinderResults = async (jobId, page = 0) => {
    setLoadingResults(true);
    try {
      const response = await resultsApi.getFinder(jobId, page * pageSize, pageSize);
      setFinderResults(response.data.results);
      setTotalResults(response.data.total);
      setCurrentPage(page);
    } catch (error) {
      console.error('Failed to load finder results:', error);
      toast.error('Failed to load results');
    } finally {
      setLoadingResults(false);
    }
  };

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
        a.download = `finder_results_${currentJob}.csv`;
        a.click();
      } else {
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `finder_results_${currentJob}.json`;
        a.click();
      }
      
      toast.success('Export successful!');
    } catch (error) {
      toast.error('Export failed');
      console.error(error);
    }
  };

  return (
    <Layout>
      <div className="space-y-6" data-testid="finder-container">
        {/* Single Email Finder */}
        <Card className="bg-surface border border-border/50 p-6">
          <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Email Pattern Finder</h2>
          <p className="text-sm text-muted-foreground mb-6">
            Find email addresses using intelligent pattern matching. We test 10 common email patterns and stop on the first valid match.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div>
              <Label className="mb-2 block">First Name</Label>
              <Input
                data-testid="first-name-input"
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="John"
                className="bg-secondary/50 border-border"
              />
            </div>
            <div>
              <Label className="mb-2 block">Last Name</Label>
              <Input
                data-testid="last-name-input"
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Doe"
                className="bg-secondary/50 border-border"
              />
            </div>
            <div>
              <Label className="mb-2 block">Domain</Label>
              <Input
                data-testid="domain-input"
                type="text"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="company.com"
                className="bg-secondary/50 border-border"
              />
            </div>
          </div>

          <Button
            data-testid="find-email-button"
            onClick={findEmail}
            disabled={searching}
            className="bg-blue-600 hover:bg-blue-700 hover:-translate-y-0.5 transition-transform"
          >
            {searching ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" strokeWidth={1.5} />}
            {searching ? 'Searching...' : 'Find Email'}
          </Button>

          {result && (
            <div className="mt-6 p-6 bg-secondary/30 rounded-md border border-border/30" data-testid="finder-result">
              {result.found ? (
                <div>
                  <div className="flex items-center space-x-2 mb-4">
                    <CheckCircle className="w-6 h-6 text-green-600" />
                    <span className="text-lg font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>Email Found!</span>
                  </div>
                  <div className="p-4 bg-background rounded-md mb-4">
                    <p className="text-2xl font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      {result.email}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground mb-1">Patterns Tested</p>
                      <p className="font-bold">{result.patterns_tested}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground mb-1">Search Time</p>
                      <p className="font-bold">{result.search_time?.toFixed(2) || 0}s</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground mb-1">Name</p>
                      <p className="font-bold">{result.first_name} {result.last_name}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="flex items-center space-x-2 mb-4">
                    <XCircle className="w-6 h-6 text-red-600" />
                    <span className="text-lg font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>No Valid Email Found</span>
                  </div>
                  <p className="text-muted-foreground mb-4">
                    Tested {result.patterns_tested} patterns in {result.search_time?.toFixed(2) || 0}s but couldn't find a valid email.
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Try different name variations or check if the domain is correct.
                  </p>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Bulk Email Finder */}
        <Card className="bg-surface border border-border/50 p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h2 className="text-xl font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>Bulk Email Finder</h2>
              <p className="text-sm text-muted-foreground mt-1">Upload CSV with first_name, last_name, and domain columns</p>
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
                <li>CSV must contain three columns: <code className="bg-secondary px-1 py-0.5 rounded">first_name</code>, <code className="bg-secondary px-1 py-0.5 rounded">last_name</code>, <code className="bg-secondary px-1 py-0.5 rounded">domain</code></li>
                <li>First row should be the header row</li>
                <li>Domain should be without http:// or www (e.g., example.com)</li>
                <li>Maximum recommended: 5,000 records per file</li>
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
              <Input
                type="file"
                accept=".csv"
                onChange={handleFileUpload}
                data-testid="bulk-finder-file-input"
                className="bg-secondary/50 border-border"
              />
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

            <div>
              <Label className="mb-2 block flex items-center">
                Threads: {threads[0]}
                <span className="ml-2 text-xs text-muted-foreground">(Concurrent searches)</span>
              </Label>
              <Slider
                data-testid="finder-threads-slider"
                value={threads}
                onValueChange={setThreads}
                min={1}
                max={50}
                step={1}
                className="w-full"
              />
            </div>
          </div>

          <div className="flex gap-2 flex-wrap">
            <Button
              data-testid="start-bulk-finder-button"
              onClick={startBulkFinder}
              disabled={bulkProcessing || !bulkFile || csvValidationError}
              className="bg-blue-600 hover:bg-blue-700 hover:-translate-y-0.5 transition-transform"
              title="Start bulk email finding"
            >
              {bulkProcessing ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Finding...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Start Finding
                </>
              )}
            </Button>
            
            {currentJob && jobStatus === 'processing' && (
              <>
                <Button
                  data-testid="pause-finder-button"
                  onClick={pauseJob}
                  variant="outline"
                  className="hover:-translate-y-0.5 transition-transform"
                  title="Pause the current job"
                >
                  <Pause className="w-4 h-4 mr-2" />
                  Pause
                </Button>
                <Button
                  data-testid="stop-finder-button"
                  onClick={stopJob}
                  variant="destructive"
                  className="hover:-translate-y-0.5 transition-transform"
                  title="Stop the current job"
                >
                  <Square className="w-4 h-4 mr-2" />
                  Stop
                </Button>
              </>
            )}
            
            {currentJob && jobStatus === 'paused' && (
              <Button
                data-testid="resume-finder-button"
                onClick={resumeJob}
                className="bg-green-600 hover:bg-green-700 hover:-translate-y-0.5 transition-transform"
                title="Resume the paused job"
              >
                <Play className="w-4 h-4 mr-2" />
                Resume
              </Button>
            )}
            
            {currentJob && (
              <>
                <Button
                  data-testid="export-finder-csv-button"
                  onClick={() => exportResults('csv')}
                  variant="outline"
                  className="hover:-translate-y-0.5 transition-transform"
                  title="Export results as CSV"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export CSV
                </Button>
                <Button
                  data-testid="export-finder-json-button"
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
            <div className="mt-6 p-4 bg-secondary/30 rounded-md border border-border/30" data-testid="finder-job-progress">
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
              
              {/* Live Counter - Current search being processed */}
              {jobStatus === 'processing' && jobProgress.current_email && (
                <div className="mb-4 p-3 bg-indigo-600/10 rounded-md border border-indigo-600/20">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Mail className="w-4 h-4 text-indigo-600 animate-pulse" />
                      <span className="text-sm font-medium text-indigo-600">Currently Searching:</span>
                    </div>
                    <span className="text-sm font-mono text-indigo-600">{jobProgress.current_email}</span>
                  </div>
                  {jobProgress.processing_rate > 0 && (
                    <div className="mt-2 text-xs text-muted-foreground flex items-center justify-end gap-1">
                      <TrendingUp className="w-3 h-3" />
                      Processing at {jobProgress.processing_rate} searches/sec
                    </div>
                  )}
                </div>
              )}
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center mb-4">
                <div className="p-3 bg-green-600/10 rounded-md border border-green-600/20">
                  <p className="text-2xl font-bold text-green-600">{jobProgress.found_count || 0}</p>
                  <p className="text-xs text-muted-foreground">Found</p>
                </div>
                <div className="p-3 bg-red-600/10 rounded-md border border-red-600/20">
                  <p className="text-2xl font-bold text-red-600">{jobProgress.not_found_count || 0}</p>
                  <p className="text-xs text-muted-foreground">Not Found</p>
                </div>
                <div className="p-3 bg-blue-600/10 rounded-md border border-blue-600/20">
                  <p className="text-2xl font-bold text-blue-600">{jobProgress.active_threads || 0}</p>
                  <p className="text-xs text-muted-foreground">Active Threads</p>
                </div>
                <div className="p-3 bg-purple-600/10 rounded-md border border-purple-600/20">
                  <p className="text-2xl font-bold text-purple-600">
                    {jobProgress.found_count > 0 && jobProgress.processed_records > 0
                      ? ((jobProgress.found_count / jobProgress.processed_records) * 100).toFixed(1)
                      : '0'}%
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
                View and download results from previous email finder jobs
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
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                          <div>
                            <span className="text-muted-foreground">Records:</span>
                            <span className="ml-1 font-mono">{job.total_records}</span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Processed:</span>
                            <span className="ml-1 font-mono">{job.processed_records || 0}</span>
                          </div>
                          <div>
                            <span className="text-green-600">Found:</span>
                            <span className="ml-1 font-mono">{job.valid_count || 0}</span>
                          </div>
                          <div>
                            <span className="text-red-600">Not Found:</span>
                            <span className="ml-1 font-mono">{job.invalid_count || 0}</span>
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
                  <p className="text-xs mt-1">Start your first bulk email finder above</p>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Results Table */}
        {currentJob && (
          <Card className="bg-surface border border-border/50 p-6" id="results-section">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h2 className="text-xl font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>Finder Results</h2>
                <p className="text-xs text-muted-foreground mt-1">
                  Showing {finderResults.length} of {totalResults} results
                </p>
              </div>
            </div>
            
            {loadingResults ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                <span className="ml-3 text-muted-foreground">Loading results...</span>
              </div>
            ) : finderResults.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-border/50">
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Name</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Domain</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Email Found</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Status</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Score</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Patterns Tested</TableHead>
                        <TableHead className="font-bold uppercase text-xs tracking-wider">Search Time</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {finderResults.map((result) => (
                        <TableRow key={result.id} className="border-border/50">
                          <TableCell className="font-medium">
                            {result.first_name} {result.last_name}
                          </TableCell>
                          <TableCell className="font-mono text-sm">{result.domain}</TableCell>
                          <TableCell className="font-mono text-sm">
                            {result.found ? (
                              <span className="text-green-600">{result.email}</span>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {result.found ? (
                              <Badge className="bg-green-600/10 text-green-600 border-green-600/20 border">
                                <CheckCircle className="w-3 h-3 mr-1" />
                                Found
                              </Badge>
                            ) : (
                              <Badge className="bg-red-600/10 text-red-600 border-red-600/20 border">
                                <XCircle className="w-3 h-3 mr-1" />
                                Not Found
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            {result.found ? getDeliverabilityScoreBadge(result.deliverability_score || 0) : <span className="text-xs text-muted-foreground">-</span>}
                          </TableCell>
                          <TableCell className="text-sm">{result.patterns_tested || 0}</TableCell>
                          <TableCell className="font-mono text-sm">
                            {result.search_time ? result.search_time.toFixed(2) : '0.00'}s
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
                        onClick={() => loadFinderResults(currentJob, currentPage - 1)}
                        disabled={currentPage === 0 || loadingResults}
                      >
                        <ChevronLeft className="w-4 h-4 mr-1" />
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => loadFinderResults(currentJob, currentPage + 1)}
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
                  Start a bulk finder job to see results here
                </p>
              </div>
            )}
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Finder;
