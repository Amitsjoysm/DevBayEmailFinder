import React, { useState, useEffect } from 'react';
import { analyticsApi } from '../lib/api';
import { Card } from '../components/ui/card';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import Layout from '../components/Layout';
import { TrendingUp, Activity, CheckCircle, XCircle } from 'lucide-react';

const Analytics = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    try {
      const response = await analyticsApi.dashboard();
      setAnalytics(response.data);
    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const COLORS = ['#2563EB', '#22C55E', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];

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
      <div className="space-y-6" data-testid="analytics-container">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="bg-surface border border-border/50 p-6" data-testid="analytics-total">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Total Verified</p>
                <p className="text-3xl font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  {analytics?.total_verified || 0}
                </p>
              </div>
              <div className="w-12 h-12 bg-blue-600/10 rounded-lg flex items-center justify-center">
                <Activity className="w-6 h-6 text-blue-600" strokeWidth={1.5} />
              </div>
            </div>
          </Card>

          <Card className="bg-surface border border-border/50 p-6" data-testid="analytics-valid">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Valid</p>
                <p className="text-3xl font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  {analytics?.total_valid || 0}
                </p>
              </div>
              <div className="w-12 h-12 bg-green-600/10 rounded-lg flex items-center justify-center">
                <CheckCircle className="w-6 h-6 text-green-600" strokeWidth={1.5} />
              </div>
            </div>
          </Card>

          <Card className="bg-surface border border-border/50 p-6" data-testid="analytics-invalid">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Invalid</p>
                <p className="text-3xl font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  {analytics?.total_invalid || 0}
                </p>
              </div>
              <div className="w-12 h-12 bg-red-600/10 rounded-lg flex items-center justify-center">
                <XCircle className="w-6 h-6 text-red-600" strokeWidth={1.5} />
              </div>
            </div>
          </Card>

          <Card className="bg-surface border border-border/50 p-6" data-testid="analytics-success-rate">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Success Rate</p>
                <p className="text-3xl font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
                  {analytics?.success_rate?.toFixed(1) || 0}%
                </p>
              </div>
              <div className="w-12 h-12 bg-purple-600/10 rounded-lg flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-purple-600" strokeWidth={1.5} />
              </div>
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="bg-surface border border-border/50 p-6" data-testid="provider-chart">
            <h3 className="text-lg font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Email Provider Distribution</h3>
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
                    label={(entry) => `${entry._id}: ${entry.count}`}
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
                No data available yet
              </div>
            )}
          </Card>

          <Card className="bg-surface border border-border/50 p-6" data-testid="status-chart">
            <h3 className="text-lg font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Verification Status Breakdown</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={[
                  { name: 'Valid', count: analytics?.total_valid || 0, fill: '#22C55E' },
                  { name: 'Invalid', count: analytics?.total_invalid || 0, fill: '#EF4444' },
                  { name: 'Risky', count: analytics?.total_risky || 0, fill: '#F59E0B' },
                ]}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#27272A" />
                <XAxis dataKey="name" stroke="#71717A" />
                <YAxis stroke="#71717A" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#18181B',
                    border: '1px solid #27272A',
                    borderRadius: '8px'
                  }}
                />
                <Bar dataKey="count" fill="#2563EB" />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </div>
    </Layout>
  );
};

export default Analytics;
