import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

interface Preference {
  id: string;
  domain: string;
  preference: string;
  confidence: string;
  strength: number;
  status: string;
  scope: string;
}

export function AgentPreferenceManager() {
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPreferences = async () => {
    try {
      const res = await api.get('/preferences');
      setPreferences(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPreferences();
  }, []);

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/preferences/${id}`);
      fetchPreferences();
    } catch (err) {
      console.error(err);
    }
  };

  const renderStrength = (strength: number) => {
    const blocks = Math.round(strength * 10);
    return '█'.repeat(blocks) + '░'.repeat(10 - blocks);
  };

  if (loading) return <div>Loading preferences...</div>;

  const grouped = preferences.reduce((acc, pref) => {
    if (!acc[pref.domain]) acc[pref.domain] = [];
    acc[pref.domain].push(pref);
    return acc;
  }, {} as Record<string, Preference[]>);

  return (
    <Card className="w-full max-w-4xl mx-auto mt-4">
      <CardHeader>
        <CardTitle>Personal Intelligence (Preferences)</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {Object.entries(grouped).map(([domain, prefs]) => (
          <div key={domain} className="space-y-2">
            <h3 className="font-semibold text-lg capitalize border-b pb-1">{domain}</h3>
            {prefs.map(p => (
              <div key={p.id} className="flex flex-col sm:flex-row justify-between p-3 border rounded-md bg-secondary/10">
                <div>
                  <p className="font-medium">{p.preference}</p>
                  <div className="text-sm text-muted-foreground flex gap-4 mt-1">
                    <span>Scope: {p.scope}</span>
                    <span>Confidence: {p.confidence}</span>
                    <span className="font-mono" title={`${(p.strength * 100).toFixed(0)}%`}>
                      Strength: {renderStrength(p.strength)}
                    </span>
                    {p.status === 'SUPERSEDED' && <span className="text-destructive">SUPERSEDED</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 mt-2 sm:mt-0">
                  <Button variant="outline" size="sm" onClick={() => handleDelete(p.id)}>Delete</Button>
                </div>
              </div>
            ))}
          </div>
        ))}
        {preferences.length === 0 && <p className="text-muted-foreground">No learned preferences yet.</p>}
      </CardContent>
    </Card>
  );
}
