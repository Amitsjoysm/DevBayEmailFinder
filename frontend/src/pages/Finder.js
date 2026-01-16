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
import { Search, Upload, CheckCircle, XCircle, Clock, Loader2, Download, Play, Pause, Square, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
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

  const handleJobProgress = (data) => {
    if (data.job_id === currentJob) {
      setJobProgress(data);
    }
  };

  const handleFinderResult = (result) => {
    setFinderResults(prev => [result, ...prev].slice(0, 100));
  };

  const handleJobCompleted = (data) => {
    if (data.job_type === 'finder' && data.job_id === currentJob) {
      toast.success('Email finding completed!');
      setBulkProcessing(false);
      loadFinderResults(data.job_id);
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
        return;
      }
      setBulkFile(file);
      toast.success(`File "${file.name}" loaded`);
    }
  };

  const startBulkFinder = async () => {
    if (!bulkFile) {
      toast.error('Please upload a CSV file');
      return;
    }

    setBulkProcessing(true);
    setFinderResults([]);
    setJobProgress(null);

    try {
      const response = await finderApi.upload(bulkFile, threads[0]);
      setCurrentJob(response.data.job_id);
      toast.success(`Finding emails for ${response.data.total_records} records`);
    } catch (error) {
      toast.error('Failed to start bulk finder');
      console.error(error);
      setBulkProcessing(false);
    }
  };

  const loadFinderResults = async (jobId) => {
    try {
      const response = await resultsApi.getFinder(jobId, 0, 100);
      setFinderResults(response.data.results);
    } catch (error) {
      console.error('Failed to load finder results:', error);
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
                      <p className="font-bold">{result.search_time.toFixed(2)}s</p>
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
                    Tested {result.patterns_tested} patterns in {result.search_time.toFixed(2)}s but couldn't find a valid email.
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
          <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Bulk Email Finder</h2>
          <p className="text-sm text-muted-foreground mb-6">
            Upload a CSV file with columns: <code className="bg-secondary/50 px-2 py-1 rounded">first_name</code>, <code className="bg-secondary/50 px-2 py-1 rounded">last_name</code>, <code className="bg-secondary/50 px-2 py-1 rounded">domain</code>
          </p>

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
              {bulkFile && (
                <p className="text-xs text-muted-foreground mt-2">
                  Selected: {bulkFile.name}
                </p>
              )}
            </div>

            <div>
              <Label className="mb-2 block">Threads: {threads[0]}</Label>
              <Slider
                data-testid="finder-threads-slider"
                value={threads}
                onValueChange={setThreads}
                min={1}
                max={50}
                step={1}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground mt-2">
                Higher threads = faster processing but more server load
              </p>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              data-testid="start-bulk-finder-button"
              onClick={startBulkFinder}
              disabled={bulkProcessing || !bulkFile}
              className="bg-blue-600 hover:bg-blue-700 hover:-translate-y-0.5 transition-transform"
            >
              <Play className="w-4 h-4 mr-2" />
              Start Finding
            </Button>
            {currentJob && (
              <>
                <Button
                  data-testid="export-finder-csv-button"
                  onClick={() => exportResults('csv')}
                  variant="outline"
                  className="hover:-translate-y-0.5 transition-transform"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export CSV
                </Button>
                <Button
                  data-testid="export-finder-json-button"
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
            <div className="mt-6 p-4 bg-secondary/30 rounded-md border border-border/30" data-testid="finder-job-progress">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium">Progress</span>
                <span className="text-sm" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  {jobProgress.processed_records}/{jobProgress.total_records}
                </span>
              </div>
              <Progress value={jobProgress.progress_percentage} className="mb-4" />
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold text-green-600">{jobProgress.found_count || 0}</p>
                  <p className="text-xs text-muted-foreground">Found</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-600">{jobProgress.not_found_count || 0}</p>
                  <p className="text-xs text-muted-foreground">Not Found</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-600">{jobProgress.error_count || 0}</p>
                  <p className="text-xs text-muted-foreground">Errors</p>
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

        {/* Results Table */}
        {finderResults.length > 0 && (
          <Card className="bg-surface border border-border/50 p-6">
            <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Recent Results</h2>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/50">
                    <TableHead className="font-bold uppercase text-xs tracking-wider">Name</TableHead>
                    <TableHead className="font-bold uppercase text-xs tracking-wider">Domain</TableHead>
                    <TableHead className="font-bold uppercase text-xs tracking-wider">Status</TableHead>
                    <TableHead className="font-bold uppercase text-xs tracking-wider">Email</TableHead>
                    <TableHead className="font-bold uppercase text-xs tracking-wider">Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {finderResults.slice(0, 20).map((result) => (
                    <TableRow key={result.id} className="border-border/50">
                      <TableCell className="font-medium">
                        {result.first_name} {result.last_name}
                      </TableCell>
                      <TableCell className="font-mono text-sm">{result.domain}</TableCell>
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
                      <TableCell className="font-mono text-sm">
                        {result.email || '-'}
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {result.search_time ? `${result.search_time.toFixed(2)}s` : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>
        )}

        {/* Email Patterns Reference */}
        <Card className="bg-surface border border-border/50 p-6">
          <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Email Patterns We Test</h2>
          <p className="text-sm text-muted-foreground mb-4">
            We automatically test these 10 common patterns in order, stopping at the first valid email:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              'first.last@domain.com',
              'firstlast@domain.com',
              'first@domain.com',
              'last@domain.com',
              'f.last@domain.com',
              'firstl@domain.com',
              'f.l@domain.com',
              'first_last@domain.com',
              'first-last@domain.com',
              'lastf@domain.com'
            ].map((pattern, index) => (
              <div key={index} className="flex items-center space-x-2 p-3 bg-secondary/30 rounded-md border border-border/30">
                <span className="text-xs font-bold text-muted-foreground w-6">{index + 1}</span>
                <code className="text-sm" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  {pattern}
                </code>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Layout>
  );
};

export default Finder;
