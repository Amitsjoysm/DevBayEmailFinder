import React, { useState, useEffect } from 'react';
import { settingsApi, proxyApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { Slider } from '../components/ui/slider';
import { Switch } from '../components/ui/switch';
import { toast } from 'sonner';
import Layout from '../components/Layout';
import { Save, Trash2 } from 'lucide-react';

const Settings = () => {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [proxies, setProxies] = useState([]);
  const [newProxy, setNewProxy] = useState({ host: '', port: '', username: '', password: '', proxy_type: 'http' });

  useEffect(() => {
    loadSettings();
    loadProxies();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await settingsApi.get();
      setSettings(response.data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadProxies = async () => {
    try {
      const response = await proxyApi.list();
      setProxies(response.data);
    } catch (error) {
      console.error('Failed to load proxies:', error);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await settingsApi.update(settings);
      toast.success('Settings saved successfully');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const addProxy = async () => {
    if (!newProxy.host || !newProxy.port) {
      toast.error('Host and port are required');
      return;
    }

    try {
      await proxyApi.add({
        ...newProxy,
        port: parseInt(newProxy.port)
      });
      toast.success('Proxy added');
      setNewProxy({ host: '', port: '', username: '', password: '', proxy_type: 'http' });
      loadProxies();
    } catch (error) {
      toast.error('Failed to add proxy');
    }
  };

  const deleteProxy = async (proxyId) => {
    try {
      await proxyApi.delete(proxyId);
      toast.success('Proxy deleted');
      loadProxies();
    } catch (error) {
      toast.error('Failed to delete proxy');
    }
  };

  if (loading || !settings) {
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
      <div className="space-y-6" data-testid="settings-container">
        <Card className="bg-surface border border-border/50 p-6">
          <h2 className="text-xl font-bold mb-6" style={{ fontFamily: 'Chivo, sans-serif' }}>Performance Settings</h2>
          
          <div className="space-y-6">
            <div>
              <Label className="mb-2 block">Concurrent Threads: {settings.threads}</Label>
              <Slider
                data-testid="settings-threads-slider"
                value={[settings.threads]}
                onValueChange={(val) => setSettings({ ...settings, threads: val[0] })}
                min={1}
                max={100}
                step={1}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground mt-1">Number of parallel verification tasks</p>
            </div>

            <div>
              <Label className="mb-2 block">Batch Size: {settings.batch_size}</Label>
              <Slider
                data-testid="settings-batch-slider"
                value={[settings.batch_size]}
                onValueChange={(val) => setSettings({ ...settings, batch_size: val[0] })}
                min={10}
                max={500}
                step={10}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground mt-1">Records per batch</p>
            </div>
          </div>
        </Card>

        <Card className="bg-surface border border-border/50 p-6">
          <h2 className="text-xl font-bold mb-6" style={{ fontFamily: 'Chivo, sans-serif' }}>Rate Limiting</h2>
          
          <div className="space-y-6">
            <div>
              <Label className="mb-2 block">Global Delay: {settings.global_delay}s</Label>
              <Slider
                data-testid="settings-global-delay-slider"
                value={[settings.global_delay]}
                onValueChange={(val) => setSettings({ ...settings, global_delay: val[0] })}
                min={0}
                max={30}
                step={1}
                className="w-full"
              />
            </div>

            <div>
              <Label className="mb-2 block">Domain Delay: {settings.domain_delay}s</Label>
              <Slider
                data-testid="settings-domain-delay-slider"
                value={[settings.domain_delay]}
                onValueChange={(val) => setSettings({ ...settings, domain_delay: val[0] })}
                min={0}
                max={30}
                step={1}
                className="w-full"
              />
            </div>

            <div>
              <Label className="mb-2 block">Server Delay: {settings.server_delay}s</Label>
              <Slider
                data-testid="settings-server-delay-slider"
                value={[settings.server_delay]}
                onValueChange={(val) => setSettings({ ...settings, server_delay: val[0] })}
                min={0}
                max={30}
                step={1}
                className="w-full"
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label>Randomize Delays</Label>
                <p className="text-xs text-muted-foreground">Add random variation to delays</p>
              </div>
              <Switch
                data-testid="settings-randomize-toggle"
                checked={settings.randomize_delays}
                onCheckedChange={(val) => setSettings({ ...settings, randomize_delays: val })}
              />
            </div>
          </div>
        </Card>

        <Card className="bg-surface border border-border/50 p-6">
          <h2 className="text-xl font-bold mb-6" style={{ fontFamily: 'Chivo, sans-serif' }}>Retry Settings</h2>
          
          <div className="space-y-6">
            <div>
              <Label className="mb-2 block">Max Retries: {settings.max_retries}</Label>
              <Slider
                data-testid="settings-max-retries-slider"
                value={[settings.max_retries]}
                onValueChange={(val) => setSettings({ ...settings, max_retries: val[0] })}
                min={0}
                max={5}
                step={1}
                className="w-full"
              />
            </div>

            <div>
              <Label className="mb-2 block">Retry Interval: {settings.retry_interval} minutes</Label>
              <Slider
                data-testid="settings-retry-interval-slider"
                value={[settings.retry_interval]}
                onValueChange={(val) => setSettings({ ...settings, retry_interval: val[0] })}
                min={1}
                max={60}
                step={1}
                className="w-full"
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label>Auto Retry</Label>
                <p className="text-xs text-muted-foreground">Automatically retry failed verifications</p>
              </div>
              <Switch
                data-testid="settings-auto-retry-toggle"
                checked={settings.auto_retry}
                onCheckedChange={(val) => setSettings({ ...settings, auto_retry: val })}
              />
            </div>
          </div>
        </Card>

        <Card className="bg-surface border border-border/50 p-6">
          <h2 className="text-xl font-bold mb-6" style={{ fontFamily: 'Chivo, sans-serif' }}>Proxy Management</h2>
          
          <div className="space-y-4 mb-6">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              <Input
                data-testid="proxy-host-input"
                placeholder="Host"
                value={newProxy.host}
                onChange={(e) => setNewProxy({ ...newProxy, host: e.target.value })}
                className="bg-secondary/50 border-border"
              />
              <Input
                data-testid="proxy-port-input"
                placeholder="Port"
                value={newProxy.port}
                onChange={(e) => setNewProxy({ ...newProxy, port: e.target.value })}
                className="bg-secondary/50 border-border"
              />
              <Input
                data-testid="proxy-username-input"
                placeholder="Username (optional)"
                value={newProxy.username}
                onChange={(e) => setNewProxy({ ...newProxy, username: e.target.value })}
                className="bg-secondary/50 border-border"
              />
              <Input
                data-testid="proxy-password-input"
                type="password"
                placeholder="Password (optional)"
                value={newProxy.password}
                onChange={(e) => setNewProxy({ ...newProxy, password: e.target.value })}
                className="bg-secondary/50 border-border"
              />
              <Button
                data-testid="add-proxy-button"
                onClick={addProxy}
                className="bg-blue-600 hover:bg-blue-700"
              >
                Add Proxy
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            {proxies.map((proxy) => (
              <div key={proxy.id} className="flex items-center justify-between p-3 bg-secondary/30 rounded-md border border-border/30">
                <div className="font-mono text-sm">
                  {proxy.host}:{proxy.port} {proxy.username && `(${proxy.username})`}
                </div>
                <Button
                  data-testid={`delete-proxy-${proxy.id}`}
                  variant="ghost"
                  size="sm"
                  onClick={() => deleteProxy(proxy.id)}
                  className="text-red-500 hover:text-red-600 hover:bg-red-500/10"
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
            {proxies.length === 0 && (
              <p className="text-center text-muted-foreground py-4">No proxies configured</p>
            )}
          </div>
        </Card>

        <div className="flex justify-end">
          <Button
            data-testid="save-settings-button"
            onClick={saveSettings}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 hover:-translate-y-0.5 transition-transform"
          >
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Saving...' : 'Save Settings'}
          </Button>
        </div>
      </div>
    </Layout>
  );
};

export default Settings;
