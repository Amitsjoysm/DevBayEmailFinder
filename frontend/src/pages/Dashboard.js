import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { analyticsApi, jobApi } from '../lib/api';
import { Card } from '../components/ui/card';
import { Activity, CheckCircle, XCircle, AlertTriangle, TrendingUp } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import Layout from '../components/Layout';

const Dashboard = () => {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [analyticsRes, jobsRes] = await Promise.all([
        analyticsApi.dashboard(),
        jobApi.list()
      ]);
      setAnalytics(analyticsRes.data);
      setJobs(jobsRes.data);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const stats = [
    {
      label: 'Total Verified',
      value: analytics?.total_verified || 0,
      icon: Activity,
      color: 'text-blue-600',
      bg: 'bg-blue-600/10'
    },
    {
      label: 'Valid Emails',
      value: analytics?.total_valid || 0,
      icon: CheckCircle,
      color: 'text-green-600',
      bg: 'bg-green-600/10'
    },
    {
      label: 'Invalid Emails',
      value: analytics?.total_invalid || 0,
      icon: XCircle,
      color: 'text-red-600',
      bg: 'bg-red-600/10'
    },
    {
      label: 'Success Rate',
      value: `${analytics?.success_rate?.toFixed(1) || 0}%`,
      icon: TrendingUp,
      color: 'text-purple-600',
      bg: 'bg-purple-600/10'
    }
  ];

  const COLORS = ['#2563EB', '#22C55E', '#F59E0B', '#EF4444', '#8B5CF6'];

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full"></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6" data-testid="dashboard-container">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {stats.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <Card key={index} className="bg-surface border border-border/50 p-6" data-testid={`stat-${stat.label.toLowerCase().replace(' ', '-')}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">{stat.label}</p>
                    <p className="text-3xl font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      {stat.value}
                    </p>
                  </div>
                  <div className={`w-12 h-12 ${stat.bg} rounded-lg flex items-center justify-center`}>
                    <Icon className={`w-6 h-6 ${stat.color}`} strokeWidth={1.5} />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-surface border border-border/50 p-6" data-testid="provider-distribution-chart">
            <h3 className="text-lg font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Provider Distribution</h3>
            {analytics?.provider_distribution?.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={analytics.provider_distribution}
                    dataKey="count"
                    nameKey="_id"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label
                  >
                    {analytics.provider_distribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-64 flex items-center justify-center text-muted-foreground">
                No data available
              </div>
            )}
          </Card>

          <Card className="bg-surface border border-border/50 p-6" data-testid="recent-jobs-list">
            <h3 className="text-lg font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Recent Jobs</h3>
            <div className="space-y-3">
              {jobs.slice(0, 5).map((job) => (
                <div key={job.id} className="flex items-center justify-between p-3 bg-secondary/30 rounded-md border border-border/30">
                  <div>
                    <p className="text-sm font-medium" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      {job.job_type === 'verification' ? 'Verification' : 'Finder'}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {job.total_records} records
                    </p>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs px-2 py-1 rounded ${
                      job.status === 'completed' ? 'bg-green-600/10 text-green-600' :
                      job.status === 'processing' ? 'bg-blue-600/10 text-blue-600' :
                      job.status === 'failed' ? 'bg-red-600/10 text-red-600' :
                      'bg-yellow-600/10 text-yellow-600'
                    }`}>
                      {job.status}
                    </span>
                    <p className="text-xs text-muted-foreground mt-1">
                      {job.processed_records}/{job.total_records}
                    </p>
                  </div>
                </div>
              ))}
              {jobs.length === 0 && (
                <div className="text-center text-muted-foreground py-8">
                  No jobs yet. Start your first verification!
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </Layout>
  );
};

export default Dashboard;
