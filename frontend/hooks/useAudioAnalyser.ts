import { useEffect, useRef, useState } from "react";

export function useAudioAnalyser() {
  const [isListening, setIsListening] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const dataArrayRef = useRef<Uint8Array | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const ownsStreamRef = useRef(true);

  const startAnalyser = async (providedStream?: MediaStream) => {
    try {
      let stream = providedStream;
      if (stream) {
        ownsStreamRef.current = false;
      } else {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        ownsStreamRef.current = true;
      }
      streamRef.current = stream;
      
      const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;
      
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      sourceRef.current = source;
      
      dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);
      setIsListening(true);
    } catch (err) {
      console.error("Microphone access denied for analyser:", err);
    }
  };

  const stopAnalyser = () => {
    if (streamRef.current) {
      if (ownsStreamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setIsListening(false);
  };

  const getFrequencies = () => {
    if (analyserRef.current && dataArrayRef.current) {
      analyserRef.current.getByteFrequencyData(dataArrayRef.current as any);
      return dataArrayRef.current;
    }
    return null;
  };

  const resumeContext = () => {
    if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume();
    }
  };

  useEffect(() => {
    return () => {
      stopAnalyser();
    };
  }, []);

  return { isListening, startAnalyser, stopAnalyser, getFrequencies, resumeContext };
}
