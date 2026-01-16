import React, { useState } from 'react';
import { finderApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Search, Upload, CheckCircle, XCircle, Clock, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import Layout from '../components/Layout';

const Finder = () => {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [domain, setDomain] = useState('');
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);

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
    } finally {
      setSearching(false);
    }
  };

  return (
    <Layout>
      <div className="space-y-6" data-testid="finder-container">
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
