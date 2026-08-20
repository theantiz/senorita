'use client';

import React from 'react';
import { Mic, MicOff, Loader2, Volume2, Square } from 'lucide-react';
import { VoiceAssistantStatus } from '@/hooks/useVoiceAssistant';

interface AgentVoiceProps {
  status: VoiceAssistantStatus;
  voiceResponse: string | null;
  manualTrigger: () => void;
  isWakeWordEnabled: boolean;
  setIsWakeWordEnabled: (enabled: boolean) => void;
}

export function AgentVoice({
  status,
  voiceResponse,
  manualTrigger,
  isWakeWordEnabled,
  setIsWakeWordEnabled,
}: AgentVoiceProps) {
  
  const getStatusDisplay = () => {
    switch (status) {
      case VoiceAssistantStatus.IDLE_LISTENING:
        return (
          <div className="flex items-center space-x-2 text-accent">
            <MicOff className="w-5 h-5" />
            <span className="text-sm font-medium">Listening for "Señorita"...</span>
          </div>
        );
      case VoiceAssistantStatus.RECORDING_COMMAND:
        return (
          <div className="flex items-center space-x-2 text-red-500 animate-pulse">
            <Mic className="w-5 h-5" />
            <span className="text-sm font-bold">Recording command...</span>
          </div>
        );
      case VoiceAssistantStatus.PROCESSING:
        return (
          <div className="flex items-center space-x-2 text-blue-500">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm font-medium">Processing...</span>
          </div>
        );
      case VoiceAssistantStatus.SPEAKING_RESPONSE:
      case VoiceAssistantStatus.GREETING:
        return (
          <div className="flex items-center space-x-2 text-green-500">
            <Volume2 className="w-5 h-5 animate-pulse" />
            <span className="text-sm font-medium line-clamp-1 flex-1">
              {voiceResponse || 'Speaking...'}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                manualTrigger(); // Cancel TTS
              }}
              className="ml-2 p-1 bg-red-100 hover:bg-red-200 text-red-700 rounded-md transition-colors"
              title="Interrupt"
            >
              <Square className="w-4 h-4" />
            </button>
          </div>
        );
      case VoiceAssistantStatus.DISABLED:
        return (
          <div className="flex items-center space-x-2 text-accent">
            <MicOff className="w-5 h-5" />
            <span className="text-sm font-medium">Voice Disabled</span>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end space-y-4">
      {/* Status Overlay */}
      {status !== VoiceAssistantStatus.DISABLED && (
        <div className="bg-white/90 backdrop-blur-md shadow-lg border border-gray-100 rounded-full py-2 px-4 flex items-center max-w-sm">
          {getStatusDisplay()}
        </div>
      )}

      {/* Main Trigger Button */}
      <div className="flex space-x-3">
        <button
          onClick={() => setIsWakeWordEnabled(!isWakeWordEnabled)}
          className={`p-3 rounded-full shadow-md transition-colors ${
            isWakeWordEnabled 
              ? 'bg-surface-clay text-secondary hover:border-border' 
              : 'bg-red-50 text-red-500 hover:bg-red-100'
          }`}
          title={isWakeWordEnabled ? "Disable Wake Word" : "Enable Wake Word"}
        >
          {isWakeWordEnabled ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
        </button>

        <button
          onClick={manualTrigger}
          disabled={status === VoiceAssistantStatus.DISABLED}
          className={`p-4 rounded-full shadow-lg transition-all transform hover:scale-105 active:scale-95 ${
            status === VoiceAssistantStatus.RECORDING_COMMAND
              ? 'bg-red-500 text-white animate-pulse'
              : status === VoiceAssistantStatus.SPEAKING_RESPONSE
              ? 'bg-green-500 text-white'
              : 'bg-black text-white hover:bg-surface-clay'
          }`}
        >
          {status === VoiceAssistantStatus.RECORDING_COMMAND ? (
            <Square className="w-6 h-6" />
          ) : status === VoiceAssistantStatus.SPEAKING_RESPONSE ? (
            <Square className="w-6 h-6" /> // Interrupt
          ) : (
            <Mic className="w-6 h-6" />
          )}
        </button>
      </div>
    </div>
  );
}
