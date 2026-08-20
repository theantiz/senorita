'use client';

import React, { useState, useEffect } from 'react';
import { Search, Trash2, Edit2, Lock, Unlock } from 'lucide-react';

export function AgentMemoryManager() {
  const [memories, setMemories] = useState<any[]>([]);
  const [query, setQuery] = useState('');
  
  // Dummy fetch for now
  useEffect(() => {
    // In real usage, this calls API /api/v1/memory
  }, []);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">Long-term Memory</h2>
          <p className="text-sm text-gray-500">Facts and preferences Señorita has learned</p>
        </div>
        <div className="relative w-64">
          <input
            type="text"
            placeholder="Search memories..."
            className="w-full pl-9 pr-4 py-2 bg-white border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
        </div>
      </div>
      
      <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
        {memories.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No memories found. Start chatting to teach Señorita.</div>
        ) : (
          memories.map((m) => (
            <div key={m.id} className="p-4 hover:bg-gray-50 transition-colors flex justify-between items-center group">
              <div>
                <div className="flex items-center space-x-2 mb-1">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 uppercase tracking-wide">
                    {m.memory_type}
                  </span>
                  <span className="text-xs text-gray-400 font-medium">
                    {m.confidence === 'HIGH' ? 'High Confidence' : m.confidence === 'MEDIUM' ? 'Medium Confidence' : 'Low Confidence'}
                  </span>
                </div>
                <p className="text-gray-800">{m.content}</p>
                <p className="text-xs text-gray-400 mt-1">Updated {new Date(m.updated_at).toLocaleDateString()}</p>
              </div>
              
              <div className="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <button className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100">
                  {m.locked ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
                </button>
                <button className="p-2 text-gray-400 hover:text-blue-600 rounded-lg hover:bg-blue-50">
                  <Edit2 className="w-4 h-4" />
                </button>
                <button className="p-2 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
