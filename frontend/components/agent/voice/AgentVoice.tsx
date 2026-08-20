import React, { useState, useEffect } from 'react';

export default function AgentVoice({ websocket }: { websocket: any }) {
  const [state, setState] = useState('OFFLINE');
  const [transcript, setTranscript] = useState('');
  
  useEffect(() => {
    if (!websocket) return;
    
    const handleMessage = (event: any) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'voice_state') {
          setState(data.state);
        } else if (data.type === 'voice_transcript') {
          setTranscript(data.text);
        }
      } catch (e) {}
    };
    
    websocket.addEventListener('message', handleMessage);
    return () => websocket.removeEventListener('message', handleMessage);
  }, [websocket]);
  
  const startVoice = () => {
    if (websocket) {
      websocket.send(JSON.stringify({ type: 'voice_start' }));
    }
  };
  
  const simulateSpeech = () => {
    if (websocket) {
      websocket.send(JSON.stringify({ type: 'voice_audio_chunk', audio_base64: 'ZmFrZV9hdWRpbw==' })); // Base64 for "fake_audio"
    }
  };
  
  const interrupt = () => {
    if (websocket) {
      websocket.send(JSON.stringify({ type: 'voice_interrupt' }));
    }
  };

  // Determine Siri-like orb colors based on state
  const getOrbStyle = () => {
    switch (state) {
      case 'LISTENING':
        return 'from-blue-400 via-indigo-500 to-purple-600 scale-110 animate-pulse shadow-[0_0_40px_rgba(79,70,229,0.6)]';
      case 'THINKING':
        return 'from-purple-500 via-pink-500 to-red-500 scale-100 animate-spin-slow shadow-[0_0_30px_rgba(219,39,119,0.5)]';
      case 'SPEAKING':
        return 'from-green-400 via-emerald-500 to-teal-600 scale-125 animate-pulse shadow-[0_0_50px_rgba(16,185,129,0.7)]';
      case 'INTERRUPTED':
        return 'from-red-400 via-orange-500 to-yellow-500 scale-95 shadow-[0_0_20px_rgba(239,68,68,0.5)]';
      default: // OFFLINE or IDLE
        return 'from-gray-600 via-gray-700 to-gray-800 scale-100 shadow-none';
    }
  };

  const getStateLabel = () => {
    switch (state) {
      case 'LISTENING': return "I'm listening...";
      case 'THINKING': return "Thinking...";
      case 'SPEAKING': return "Señorita is speaking...";
      case 'INTERRUPTED': return "Interrupted.";
      case 'OFFLINE': return "Offline";
      case 'IDLE': return "Ready";
      default: return state;
    }
  };

  return (
    <div className="bg-black/95 text-white rounded-3xl shadow-2xl p-8 flex flex-col items-center justify-center min-h-[300px] border border-white/10 relative overflow-hidden">
      
      {/* Background ambient glow matching the orb */}
      <div className={`absolute inset-0 opacity-20 bg-gradient-to-br transition-all duration-700 blur-3xl ${getOrbStyle()}`}></div>

      {/* Siri-like Orb */}
      <div className="relative flex items-center justify-center w-32 h-32 mb-8 z-10">
        <div className={`absolute inset-0 rounded-full bg-gradient-to-tr transition-all duration-700 ${getOrbStyle()}`}></div>
        
        {/* Inner core to give it a 3D glass effect */}
        <div className="absolute inset-2 rounded-full bg-black/20 backdrop-blur-sm border border-white/20"></div>
        
        {/* Microphone Icon shown only when idle/listening */}
        {(state === 'IDLE' || state === 'OFFLINE') && (
          <svg className="w-8 h-8 text-white/50 z-20" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"></path></svg>
        )}
      </div>
      
      {/* State Text */}
      <h2 className="text-2xl font-light tracking-wide mb-2 text-white/90 z-10">{getStateLabel()}</h2>
      
      {/* Live Transcript Display */}
      <div className="h-16 flex items-center justify-center w-full max-w-md px-4 z-10">
        <p className={`text-center text-lg transition-opacity duration-300 ${transcript ? 'opacity-100 text-white font-medium' : 'opacity-0'}`}>
          "{transcript}"
        </p>
      </div>
      
      {/* Developer Controls (Hidden in production, but useful for testing) */}
      <div className="flex space-x-3 mt-8 z-10">
        <button onClick={startVoice} className="bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/10 hover:bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/20 text-white/80 backdrop-blur-md border border-white/10 px-5 py-2 rounded-full text-sm font-medium transition-all">Wake Señorita</button>
        <button onClick={simulateSpeech} className="bg-blue-500/20 hover:bg-blue-500/30 text-blue-300 border border-blue-500/30 px-5 py-2 rounded-full text-sm font-medium transition-all">Push to Talk</button>
        {state === 'SPEAKING' && (
          <button onClick={interrupt} className="bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 px-5 py-2 rounded-full text-sm font-medium transition-all">Interrupt</button>
        )}
      </div>
    </div>
  );
}
