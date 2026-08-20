import React, { useState, useEffect, useRef } from 'react';

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

  return (
    <div className="bg-gray-900 text-white rounded-xl shadow-lg p-6 flex flex-col items-center">
      <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 ${
        state === 'LISTENING' ? 'bg-blue-500 animate-pulse' :
        state === 'SPEAKING' ? 'bg-green-500 animate-bounce' :
        state === 'THINKING' ? 'bg-yellow-500 animate-pulse' : 'bg-gray-700'
      }`}>
        🎙️
      </div>
      <h2 className="text-xl font-bold mb-1">SEÑORITA</h2>
      <p className="text-gray-400 text-sm mb-4">{state}</p>
      
      {transcript && <p className="italic text-gray-300 text-center mb-4">"{transcript}"</p>}
      
      <div className="flex space-x-2">
        <button onClick={startVoice} className="bg-gray-700 px-3 py-1 rounded text-sm hover:bg-gray-600">Start Session</button>
        <button onClick={simulateSpeech} className="bg-blue-600 px-3 py-1 rounded text-sm hover:bg-blue-500">Push to Talk</button>
        {state === 'SPEAKING' && <button onClick={interrupt} className="bg-red-600 px-3 py-1 rounded text-sm hover:bg-red-500">Stop</button>}
      </div>
    </div>
  );
}
