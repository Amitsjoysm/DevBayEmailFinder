import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Zap, ShieldCheck, Activity, Database, Server, BarChart3, Search, Gauge } from 'lucide-react';

const Landing = () => {
  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b border-border/50 bg-background/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                <Zap className="w-6 h-6 text-white" strokeWidth={1.5} />
              </div>
              <span className="text-xl font-bold" style={{ fontFamily: 'Chivo, sans-serif' }}>VerifyMail</span>
            </div>
            <div className="flex items-center space-x-4">
              <Link to="/login">
                <Button variant="ghost" data-testid="nav-login-button" className="hover:-translate-y-0.5 transition-transform">Sign In</Button>
              </Link>
              <Link to="/register">
                <Button data-testid="nav-register-button" className="bg-blue-600 hover:bg-blue-700 hover:-translate-y-0.5 transition-transform">Get Started</Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <div 
        className="relative overflow-hidden"
        style={{
          background: `linear-gradient(rgba(9, 9, 11, 0.95), rgba(9, 9, 11, 0.95)), url('https://images.unsplash.com/photo-1762279388956-1c098163a2a8?crop=entropy&cs=srgb&fm=jpg&q=85')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center'
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 sm:py-32">
          <div className="text-center max-w-4xl mx-auto">
            <h1 
              className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6" 
              style={{ fontFamily: 'Chivo, sans-serif' }}
              data-testid="hero-title"
            >
              Email Verification at Scale
            </h1>
            <p className="text-lg sm:text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
              Process 10K+ emails with intelligent pattern detection, multi-provider identification, and advanced async processing.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link to="/register">
                <Button 
                  data-testid="hero-get-started-button"
                  size="lg" 
                  className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-8 h-12 rounded-md hover:-translate-y-0.5 transition-transform"
                >
                  Start Verifying
                </Button>
              </Link>
              <Button 
                data-testid="hero-learn-more-button"
                size="lg" 
                variant="outline" 
                className="border-border/50 hover:border-blue-600 h-12 px-8 rounded-md hover:-translate-y-0.5 transition-transform"
              >
                View Features
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
          <div className="md:col-span-8 bg-surface border border-border/50 rounded-lg p-8 hover:border-blue-600/50 transition-colors" data-testid="feature-bulk-processing">
            <div className="flex items-start space-x-4">
              <div className="w-12 h-12 bg-blue-600/10 rounded-lg flex items-center justify-center flex-shrink-0">
                <Database className="w-6 h-6 text-blue-600" strokeWidth={1.5} />
              </div>
              <div>
                <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Chivo, sans-serif' }}>Bulk Processing Engine</h3>
                <p className="text-muted-foreground mb-4">
                  Process 10K+ records asynchronously with configurable threading (1-100 threads), batch processing, and real-time progress tracking.
                </p>
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs px-2 py-1 bg-blue-600/10 text-blue-600 rounded">Async Queue</span>
                  <span className="text-xs px-2 py-1 bg-blue-600/10 text-blue-600 rounded">10K+ Records</span>
                  <span className="text-xs px-2 py-1 bg-blue-600/10 text-blue-600 rounded">Real-time ETA</span>
                </div>
              </div>
            </div>
          </div>

          <div className="md:col-span-4 bg-surface border border-border/50 rounded-lg p-8 hover:border-blue-600/50 transition-colors" data-testid="feature-patterns">
            <div className="w-12 h-12 bg-green-600/10 rounded-lg flex items-center justify-center mb-4">
              <Search className="w-6 h-6 text-green-600" strokeWidth={1.5} />
            </div>
            <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Chivo, sans-serif' }}>10 Email Patterns</h3>
            <p className="text-muted-foreground text-sm">
              Smart finder with pattern caching and domain-specific learning.
            </p>
          </div>

          <div className="md:col-span-4 bg-surface border border-border/50 rounded-lg p-8 hover:border-blue-600/50 transition-colors" data-testid="feature-providers">
            <div className="w-12 h-12 bg-purple-600/10 rounded-lg flex items-center justify-center mb-4">
              <ShieldCheck className="w-6 h-6 text-purple-600" strokeWidth={1.5} />
            </div>
            <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Chivo, sans-serif' }}>Provider Detection</h3>
            <p className="text-muted-foreground text-sm">
              Identify Gmail, Outlook, O365, Yahoo, Zoho, and 6+ more providers.
            </p>
          </div>

          <div className="md:col-span-8 bg-surface border border-border/50 rounded-lg p-8 hover:border-blue-600/50 transition-colors" data-testid="feature-verification">
            <div className="flex items-start space-x-4">
              <div className="w-12 h-12 bg-orange-600/10 rounded-lg flex items-center justify-center flex-shrink-0">
                <Server className="w-6 h-6 text-orange-600" strokeWidth={1.5} />
              </div>
              <div>
                <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Chivo, sans-serif' }}>Dual Verification System</h3>
                <p className="text-muted-foreground mb-4">
                  SMTP handshake verification with MX record checks, plus fallback to external API for maximum accuracy. Catch-all detection included.
                </p>
                <div className="flex flex-wrap gap-2">
                  <span className="text-xs px-2 py-1 bg-orange-600/10 text-orange-600 rounded">SMTP Verify</span>
                  <span className="text-xs px-2 py-1 bg-orange-600/10 text-orange-600 rounded">API Fallback</span>
                  <span className="text-xs px-2 py-1 bg-orange-600/10 text-orange-600 rounded">Catch-all Detection</span>
                </div>
              </div>
            </div>
          </div>

          <div className="md:col-span-6 bg-surface border border-border/50 rounded-lg p-8 hover:border-blue-600/50 transition-colors" data-testid="feature-threading">
            <div className="w-12 h-12 bg-cyan-600/10 rounded-lg flex items-center justify-center mb-4">
              <Gauge className="w-6 h-6 text-cyan-600" strokeWidth={1.5} />
            </div>
            <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Chivo, sans-serif' }}>Thread Management</h3>
            <p className="text-muted-foreground text-sm mb-3">
              Configure concurrency from 1-100 threads with smart rate limiting and domain-specific delays.
            </p>
            <div className="text-2xl font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>1-100 Threads</div>
          </div>

          <div className="md:col-span-6 bg-surface border border-border/50 rounded-lg p-8 hover:border-blue-600/50 transition-colors" data-testid="feature-analytics">
            <div className="w-12 h-12 bg-pink-600/10 rounded-lg flex items-center justify-center mb-4">
              <BarChart3 className="w-6 h-6 text-pink-600" strokeWidth={1.5} />
            </div>
            <h3 className="text-xl font-bold mb-2" style={{ fontFamily: 'Chivo, sans-serif' }}>Real-time Analytics</h3>
            <p className="text-muted-foreground text-sm mb-3">
              Track success rates, provider distribution, and verification speed with live dashboards.
            </p>
            <div className="text-2xl font-bold" style={{ fontFamily: 'JetBrains Mono, monospace' }}>&lt;500ms avg</div>
          </div>
        </div>

        <div className="mt-16 bg-blue-600/5 border border-blue-600/20 rounded-lg p-12 text-center">
          <h2 className="text-3xl font-bold mb-4" style={{ fontFamily: 'Chivo, sans-serif' }}>Ready to Start?</h2>
          <p className="text-muted-foreground mb-8 max-w-2xl mx-auto">
            Join teams processing millions of email verifications. Get started in under 2 minutes.
          </p>
          <Link to="/register">
            <Button 
              data-testid="cta-get-started-button"
              size="lg" 
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-8 h-12 rounded-md hover:-translate-y-0.5 transition-transform"
            >
              Start Free Trial
            </Button>
          </Link>
        </div>
      </div>

      <footer className="border-t border-border/50 py-12 mt-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center text-sm text-muted-foreground">
            <p>© 2025 VerifyMail. Built with precision.</p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
