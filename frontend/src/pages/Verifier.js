import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { verifyApi, resultsApi } from '../lib/api';
import { getSocket } from '../lib/socket';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { Progress } from '../components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Slider } from '../components/ui/slider';
import { Badge } from '../components/ui/badge';
import { Upload, Mail, Play, Pause, Square, Download, CheckCircle, XCircle, AlertTriangle, Loader2 } from 'lucide-react';
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

  const handleJobProgress = (data) => {
    setJobProgress(data);
  };

  const handleVerificationResult = (result) => {
    setResults(prev => [result, ...prev].slice(0, 100));
  };

  const handleJobCompleted = (data) => {
    toast.success('Verification completed!');
    setBulkProcessing(false);
    loadResults(data.job_id);
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
        return;
      }
      setBulkFile(file);
      toast.success(`File "${file.name}" loaded`);
    }
  };

  const startBulkVerification = async () => {
    if (!bulkFile) {
      toast.error('Please upload a CSV file');
      return;
    }

    setBulkProcessing(true);
    setResults([]);

    try {
      const response = await verifyApi.upload(bulkFile, threads[0], delay[0]);
      setCurrentJob(response.data.job_id);
      toast.success(`Processing ${response.data.total_records} emails`);
    } catch (error) {
      toast.error('Failed to start verification');
      setBulkProcessing(false);
    }
  };

  const loadResults = async (jobId) => {
    try {
      const response = await resultsApi.get(jobId, 0, 100);
      setResults(response.data.results);
    } catch (error) {
      console.error('Failed to load results:', error);
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
          <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Bulk Verification</h2>
          
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
              {bulkFile && (
                <p className="text-xs text-muted-foreground mt-2">
                  Selected: {bulkFile.name}
                </p>
              )}
            </div>

            <div className="space-y-4">
              <div>
                <Label className="mb-2 block">Threads: {threads[0]}</Label>
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
                <Label className="mb-2 block">Delay: {delay[0]}s</Label>
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

          <div className="flex gap-2">
            <Button
              data-testid="start-bulk-button"
              onClick={startBulkVerification}
              disabled={bulkProcessing || !bulkFile}
              className="bg-blue-600 hover:bg-blue-700 hover:-translate-y-0.5 transition-transform"
            >
              <Play className="w-4 h-4 mr-2" />
              Start Verification
            </Button>
            {currentJob && (
              <>
                <Button
                  data-testid="export-csv-button"
                  onClick={() => exportResults('csv')}
                  variant="outline"
                  className="hover:-translate-y-0.5 transition-transform"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export CSV
                </Button>
                <Button
                  data-testid="export-json-button"
                  onClick={() => exportResults('json')}
                  variant="outline"
                  className="hover:-translate-y-0.5 transition-transform"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export JSON
                </Button>
              </>
            )}
          </div>

          {jobProgress && (
            <div className="mt-6 p-4 bg-secondary/30 rounded-md border border-border/30" data-testid="job-progress">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium">Progress</span>
                <span className="text-sm" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  {jobProgress.processed_records}/{jobProgress.total_records}
                </span>
              </div>
              <Progress value={jobProgress.progress_percentage} className="mb-4" />
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-green-600">{jobProgress.valid_count}</p>
                  <p className="text-xs text-muted-foreground">Valid</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-600">{jobProgress.invalid_count}</p>
                  <p className="text-xs text-muted-foreground">Invalid</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-yellow-600">{jobProgress.risky_count}</p>
                  <p className="text-xs text-muted-foreground">Risky</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-600">{jobProgress.unknown_count}</p>
                  <p className="text-xs text-muted-foreground">Unknown</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-blue-600">{jobProgress.active_threads}</p>
                  <p className="text-xs text-muted-foreground">Active Threads</p>
                </div>
              </div>
              {jobProgress.eta_seconds && (
                <p className="text-center text-sm text-muted-foreground mt-4">
                  ETA: {Math.floor(jobProgress.eta_seconds / 60)}m {jobProgress.eta_seconds % 60}s
                </p>
              )}
            </div>
          )}
        </Card>

        {results.length > 0 && (
          <Card className="bg-surface border border-border/50 p-6">
            <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Recent Results</h2>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/50">
                    <TableHead className="font-bold uppercase text-xs tracking-wider">Email</TableHead>
                    <TableHead className="font-bold uppercase text-xs tracking-wider">Status</TableHead>
                    <TableHead className="font-bold uppercase text-xs tracking-wider">Provider</TableHead>
                    <TableHead className="font-bold uppercase text-xs tracking-wider">Response Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.slice(0, 20).map((result) => (
                    <TableRow key={result.id} className="border-border/50">
                      <TableCell className="font-mono text-sm">{result.email}</TableCell>
                      <TableCell>{getStatusBadge(result.status)}</TableCell>
                      <TableCell>{getProviderBadge(result.provider)}</TableCell>
                      <TableCell className="font-mono text-sm">
                        {(result.response_time * 1000).toFixed(0)}ms
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>
        )}
      </div>
    </Layout>
  );
};

export default Verifier;
