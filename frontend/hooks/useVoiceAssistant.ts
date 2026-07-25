import { useState, useRef, useEffect, useCallback } from 'react';
import { sendVoiceMessage, speakText } from '@/lib/api';

declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export enum VoiceAssistantStatus {
  DISABLED          = 'DISABLED',
  IDLE_LISTENING    = 'IDLE_LISTENING',
  WAKE_DETECTED     = 'WAKE_DETECTED',
  GREETING          = 'GREETING',
  RECORDING_COMMAND = 'RECORDING_COMMAND',
  PROCESSING        = 'PROCESSING',
  SPEAKING_RESPONSE = 'SPEAKING_RESPONSE',
  ERROR_RECOVERY    = 'ERROR_RECOVERY',
}

// ─── Wake triggers (EN + Hindi phonetics) ────────────────────────────────────
const WAKE_TRIGGERS = [
  'senorita', 'señorita', 'seniorita', 'senoritha', 'senirita',
  'baby girl', 'babygirl', 'baby gurl',
  'sun re', 'sunre',
  'hey senorita',
];

// ─── Chrome TTS keepalive ─────────────────────────────────────────────────────
let _keepalive: ReturnType<typeof setInterval> | null = null;
function startKeepalive() {
  if (_keepalive) return;
  _keepalive = setInterval(() => {
    if (window.speechSynthesis?.speaking) {
      window.speechSynthesis.pause();
      window.speechSynthesis.resume();
    } else stopKeepalive();
  }, 10_000);
}
function stopKeepalive() {
  if (_keepalive) { clearInterval(_keepalive); _keepalive = null; }
}

// ─── Browser TTS fallback helpers ─────────────────────────────────────────────
const MALE_NAMES   = ['Daniel', 'Alex', 'Fred', 'Aaron', 'Rishi', 'Arthur', 'Bruce', 'Tom', 'George'];
const FEMALE_NAMES = ['Samantha', 'Veena', 'Moira', 'Tessa', 'Karen', 'Victoria', 'Lekha', 'Kalpana', 'Heera', 'Aditi', 'Zira', 'Ava', 'Siri', 'Aria'];

function isMaleVoice(v: SpeechSynthesisVoice)     { return MALE_NAMES.some(n => v.name.includes(n))   || v.name.toLowerCase().includes('male'); }
function isFemaleVoice(v: SpeechSynthesisVoice)   { return FEMALE_NAMES.some(n => v.name.includes(n)) || v.name.toLowerCase().includes('female'); }
function isEnhancedVoice(v: SpeechSynthesisVoice) { return /Enhanced|Premium|Neural/i.test(v.name); }

let _cachedVoice: SpeechSynthesisVoice | null = null;

function pickFallbackVoice(): SpeechSynthesisVoice | null {
  if (_cachedVoice) return _cachedVoice;
  const allVoices = window.speechSynthesis?.getVoices() ?? [];
  // Prefer en-US female voices to match backend AriaNeural
  const voices = allVoices.filter(v => !v.name.toLowerCase().includes('google'));
  if (!voices.length) return null;
  _cachedVoice =
    voices.find(v => v.lang === 'en-US' && isFemaleVoice(v) && isEnhancedVoice(v)) ??
    voices.find(v => v.lang === 'en-US' && isFemaleVoice(v)) ??
    voices.find(v => v.lang.startsWith('en') && isFemaleVoice(v) && isEnhancedVoice(v)) ??
    voices.find(v => v.lang.startsWith('en') && isFemaleVoice(v)) ??
    voices.find(v => isFemaleVoice(v) && isEnhancedVoice(v)) ??
    voices.find(v => isFemaleVoice(v)) ??
    voices[0] ?? null;
  if (_cachedVoice) console.log('[Senorita] Fallback voice selected:', _cachedVoice.name, _cachedVoice.lang);
  return _cachedVoice;
}

// ─── Smart sentence splitter ──────────────────────────────────────────────────
function splitChunks(text: string): string[] {
  const clean = text.replace(/[*_#`]/g, '').trim();
  const sentences = clean.match(/[^.?!;—]+[.?!;—]+|[^.?!;—]+$/g) ?? [clean];
  const out: string[] = [];
  for (const s of sentences) {
    const t = s.trim();
    if (!t) continue;
    if (t.length <= 140) { out.push(t); continue; }
    let acc = '';
    for (const p of t.split(/,\s*/)) {
      if ((acc + p).length > 130 && acc) { out.push(acc.trim()); acc = p; }
      else acc = acc ? `${acc}, ${p}` : p;
    }
    if (acc) out.push(acc.trim());
  }
  return out.filter(Boolean);
}

// ─── Hook ──────────────────────────────────────────────────────────────────────
interface UseVoiceAssistantProps {
  token: string | null;
  onCommandProcessed: (transcription?: string, response?: string) => void;
  getFrequencies: () => Uint8Array | null;
}

export function useVoiceAssistant({ token, onCommandProcessed, getFrequencies }: UseVoiceAssistantProps) {
  const [status, setStatus]                   = useState<VoiceAssistantStatus>(VoiceAssistantStatus.IDLE_LISTENING);
  const [voiceResponse, setVoiceResponse]     = useState<string | null>(null);
  const [isWakeWordEnabled, setIsWakeWordEnabled] = useState(true);
  const [activeStream, setActiveStream]       = useState<MediaStream | null>(null);

  // ── Refs that are safe to read from any stale closure ─────────────────────
  const statusRef          = useRef<VoiceAssistantStatus>(VoiceAssistantStatus.IDLE_LISTENING);
  const wakeEnabledRef     = useRef(true);
  const recognitionRef     = useRef<any>(null);
  const mediaRecorderRef   = useRef<MediaRecorder | null>(null);
  const audioChunksRef     = useRef<BlobPart[]>([]);
  const vadFrameRef        = useRef<number | null>(null);
  const lastWakeRef        = useRef(0);
  const activeStreamRef    = useRef<MediaStream | null>(null);
  const isSpeakingRef      = useRef(false);
  const retryRef           = useRef(0);
  const tokenRef           = useRef(token);
  const onCommandRef       = useRef(onCommandProcessed);
  const getFreqRef         = useRef(getFrequencies);
  const audioRef           = useRef<HTMLAudioElement | null>(null);

  // Keep refs in sync with props/state every render
  useEffect(() => { statusRef.current = status; },            [status]);
  useEffect(() => { wakeEnabledRef.current = isWakeWordEnabled; }, [isWakeWordEnabled]);
  useEffect(() => { tokenRef.current = token; },              [token]);
  useEffect(() => { onCommandRef.current = onCommandProcessed; }, [onCommandProcessed]);
  useEffect(() => { getFreqRef.current = getFrequencies; },   [getFrequencies]);

  // ── Preload fallback voices ───────────────────────────────────────────────
  useEffect(() => {
    const load = () => { _cachedVoice = null; pickFallbackVoice(); };
    window.speechSynthesis?.addEventListener('voiceschanged', load);
    if ((window.speechSynthesis?.getVoices().length ?? 0) > 0) load();
    return () => window.speechSynthesis?.removeEventListener('voiceschanged', load);
  }, []);

  // ── Core audio playback helper ────────────────────────────────────────────
  const playAudioBase64 = useCallback((audioBase64: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
      audioRef.current = audio;
      audio.onended = () => { audioRef.current = null; resolve(); };
      audio.onerror = (e) => { audioRef.current = null; reject(e); };
      audio.play().catch(reject);
    });
  }, []);

  // ── Browser TTS fallback (single chunk) ──────────────────────────────────
  const speakChunkFallback = useCallback((text: string): Promise<void> => new Promise(res => {
    const utt = new SpeechSynthesisUtterance(text);
    const v   = pickFallbackVoice();
    if (v) utt.voice = v;
    utt.pitch  = 1.05;
    utt.rate   = 0.93;
    utt.volume = 1.0;
    utt.onend   = () => res();
    utt.onerror = () => res();
    window.speechSynthesis.speak(utt);
  }), []);

  // ── Unified speak: backend edge-tts → fallback browser TTS ───────────────
  /**
   * Always uses the backend en-US-AriaNeural voice when a token is available.
   * Falls back to browser SpeechSynthesis only if the backend call fails.
   */
  const speakWithBackend = useCallback(async (text: string): Promise<void> => {
    const tok = tokenRef.current ?? (typeof window !== 'undefined' ? localStorage.getItem('senorita_token') : null);

    if (tok) {
      try {
        const audioBase64 = await speakText(tok, text);
        if (audioBase64) {
          await playAudioBase64(audioBase64);
          return;
        }
      } catch {
        // fall through to browser TTS
      }
    }

    // Browser TTS fallback
    if (!window.speechSynthesis) return;
    const chunks = splitChunks(text);
    startKeepalive();
    for (const chunk of chunks) {
      if (!isSpeakingRef.current) break;
      await speakChunkFallback(chunk);
      await new Promise(r => setTimeout(r, 80));
    }
    stopKeepalive();
  }, [playAudioBase64, speakChunkFallback]);

  // ── Cancel all active speech ──────────────────────────────────────────────
  const cancelTTS = useCallback(() => {
    stopKeepalive();
    isSpeakingRef.current = false;
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    try { window.speechSynthesis?.cancel(); } catch { /* noop */ }
  }, []);

  // ── Speak full response (voice command reply) ─────────────────────────────
  const speakResponse = useCallback(async (text: string, audioBase64?: string) => {
    setStatus(VoiceAssistantStatus.SPEAKING_RESPONSE);

    // Cancel any existing speech
    stopKeepalive();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    try { window.speechSynthesis?.cancel(); } catch { /* noop */ }

    await new Promise(r => setTimeout(r, 80));
    isSpeakingRef.current = true;

    // If the voice endpoint already returned audio, play it directly
    if (audioBase64) {
      try {
        await playAudioBase64(audioBase64);
        isSpeakingRef.current = false;
        setVoiceResponse(null);
        setStatus(VoiceAssistantStatus.IDLE_LISTENING);
        return;
      } catch (e) {
        console.error('[Senorita] Audio playback error, falling back to backend TTS:', e);
      }
    }

    // Otherwise request TTS from the backend (same Aria voice)
    await speakWithBackend(text);

    isSpeakingRef.current = false;
    setVoiceResponse(null);
    setStatus(VoiceAssistantStatus.IDLE_LISTENING);
  }, [playAudioBase64, speakWithBackend]);

  // ── Stop recognition ──────────────────────────────────────────────────────
  const stopRecognition = useCallback((): Promise<void> => new Promise(res => {
    const rec = recognitionRef.current;
    if (!rec) return res();
    const done = () => res();
    rec.onend   = done;
    rec.onerror = done;
    try { rec.stop(); } catch { res(); }
    recognitionRef.current = null;
  }), []);

  const releaseStream = useCallback(() => {
    activeStreamRef.current?.getTracks().forEach(t => t.stop());
    activeStreamRef.current = null;
    setActiveStream(null);
  }, []);

  // ── Process recorded audio blob ───────────────────────────────────────────
  const processCommand = useCallback(async () => {
    setStatus(VoiceAssistantStatus.PROCESSING);
    setVoiceResponse('PROCESSING...');

    releaseStream();
    if (vadFrameRef.current) { cancelAnimationFrame(vadFrameRef.current); vadFrameRef.current = null; }

    const mime  = mediaRecorderRef.current?.mimeType ?? 'audio/webm';
    const blob  = new Blob(audioChunksRef.current, { type: mime });
    audioChunksRef.current = [];

    const tok = tokenRef.current ?? (typeof window !== 'undefined' ? localStorage.getItem('senorita_token') : null);
    if (!tok || blob.size < 300) {
      console.warn('[Senorita] Blob too small or no token — skipping:', blob.size);
      setVoiceResponse(null);
      setStatus(VoiceAssistantStatus.IDLE_LISTENING);
      return;
    }

    const fd = new FormData();
    fd.append('audio', blob, 'voice.webm');

    try {
      const res = await sendVoiceMessage(tok, fd);
      retryRef.current = 0;
      console.log('[Senorita] Response:', res.response?.slice(0, 80));
      setVoiceResponse(res.response);
      onCommandRef.current(res.transcription, res.response);
      await speakResponse(res.response, res.audio_base64);
    } catch (err) {
      console.error('[Senorita] API error:', err);
      const msg = 'I lost the uplink. Try again.';
      setVoiceResponse('UPLINK FAILURE');
      onCommandRef.current(undefined, msg);
      await speakResponse(msg);
    }
  }, [releaseStream, speakResponse]);

  // ── Start recording with adaptive VAD ────────────────────────────────────
  const startRecordingCommand = useCallback(async () => {
    setStatus(VoiceAssistantStatus.RECORDING_COMMAND);
    setVoiceResponse('LISTENING...');
    console.log('[Senorita] Recording started');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true }
      });
      activeStreamRef.current = stream;
      setActiveStream(stream);

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current   = [];

      recorder.ondataavailable = e => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      recorder.onstop          = () => processCommand();

      recorder.start(100);

      // ── Adaptive VAD with EMA smoothing ─────────────────────────────────
      let emaVol       = 0;
      let hasSpoken    = false;
      let silenceStart = Date.now();
      const recStart   = Date.now();

      const checkSilence = () => {
        if (statusRef.current !== VoiceAssistantStatus.RECORDING_COMMAND) return;
        if (mediaRecorderRef.current?.state !== 'recording') return;

        const freqs = getFreqRef.current();
        let peak = 0;
        if (freqs) for (let i = 0; i < freqs.length; i++) if (freqs[i] > peak) peak = freqs[i];

        emaVol = 0.15 * peak + 0.85 * emaVol;

        if (emaVol > 22) { hasSpoken = true; silenceStart = Date.now(); }

        const silencedFor = Date.now() - silenceStart;
        const elapsed     = Date.now() - recStart;

        const shouldStop =
          (hasSpoken  && silencedFor > 2200) ||
          (!hasSpoken && silencedFor > 9000) ||
          elapsed > 20_000;

        if (shouldStop) {
          console.log('[Senorita] VAD stop — hasSpoken:', hasSpoken, 'silenced:', silencedFor);
          if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
        } else {
          vadFrameRef.current = requestAnimationFrame(checkSilence);
        }
      };

      vadFrameRef.current = requestAnimationFrame(checkSilence);

    } catch (err: any) {
      console.error('[Senorita] getUserMedia error:', err);
      releaseStream();
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        setVoiceResponse('MIC PERMISSION DENIED');
        setStatus(VoiceAssistantStatus.DISABLED);
      } else {
        const delay = Math.min(1000 * 2 ** retryRef.current, 12_000);
        retryRef.current++;
        setStatus(VoiceAssistantStatus.ERROR_RECOVERY);
        setTimeout(() => setStatus(VoiceAssistantStatus.IDLE_LISTENING), delay);
      }
    }
  }, [processCommand, releaseStream]);

  // ── Greeting (wake word response) ─────────────────────────────────────────
  const playGreeting = useCallback(async () => {
    cancelTTS();
    const GREETINGS = [
      "Hey Jay.",
      "Yes, Jay?",
      "I'm here, Jay.",
      "How can I help you, Jay?",
      "At your service, Jay.",
      "What's up, Jay?",
    ];
    isSpeakingRef.current = true;
    await speakWithBackend(GREETINGS[Math.floor(Math.random() * GREETINGS.length)]);
    isSpeakingRef.current = false;
    await new Promise(r => setTimeout(r, 150));
  }, [cancelTTS, speakWithBackend]);

  // ── Wake-word handler ─────────────────────────────────────────────────────
  const handleWakeWord = useCallback(async () => {
    if (statusRef.current !== VoiceAssistantStatus.IDLE_LISTENING) return;
    console.log('[Senorita] Wake word detected!');

    setStatus(VoiceAssistantStatus.WAKE_DETECTED);
    await stopRecognition();
    setStatus(VoiceAssistantStatus.GREETING);
    await playGreeting();
    startRecordingCommand();
  }, [stopRecognition, playGreeting, startRecordingCommand]);

  // ── Idle SpeechRecognition (wake-word listener) ───────────────────────────
  const startIdleListening = useCallback(async () => {
    if (!wakeEnabledRef.current) return;
    if (statusRef.current !== VoiceAssistantStatus.IDLE_LISTENING) return;

    await stopRecognition();

    const SpeechRec = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SpeechRec) {
      console.warn('[Senorita] SpeechRecognition not supported.');
      setStatus(VoiceAssistantStatus.DISABLED);
      return;
    }

    const rec = new SpeechRec();
    rec.continuous     = true;
    rec.interimResults = true;
    rec.lang           = 'en-US';

    rec.onresult = (event: any) => {
      if (statusRef.current !== VoiceAssistantStatus.IDLE_LISTENING) return;
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const txt = event.results[i][0].transcript.toLowerCase().trim();
        if (WAKE_TRIGGERS.some(t => txt.includes(t))) {
          const now = Date.now();
          if (now - lastWakeRef.current > 3000) {
            lastWakeRef.current = now;
            handleWakeWord();
            return;
          }
        }
      }
    };

    rec.onerror = (e: any) => {
      console.warn('[Senorita] Recognition error:', e.error);
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        setStatus(VoiceAssistantStatus.DISABLED);
        setVoiceResponse('MIC PERMISSION DENIED');
        return;
      }
      rec.onend = () => {};
      const delay = e.error === 'network'
        ? Math.min(1000 * 2 ** retryRef.current++, 12_000)
        : 400;
      setTimeout(() => {
        if (statusRef.current === VoiceAssistantStatus.IDLE_LISTENING) startIdleListening();
      }, delay);
    };

    rec.onend = () => {
      if (statusRef.current === VoiceAssistantStatus.IDLE_LISTENING && wakeEnabledRef.current) {
        setTimeout(() => {
          if (statusRef.current === VoiceAssistantStatus.IDLE_LISTENING) startIdleListening();
        }, 300);
      }
    };

    try {
      rec.start();
      recognitionRef.current = rec;
      console.log('[Senorita] Idle listening started');
    } catch (e) {
      console.error('[Senorita] Failed to start recognition:', e);
    }
  }, [stopRecognition, handleWakeWord]);

  // ── Drive idle listening from status transitions ───────────────────────────
  useEffect(() => {
    if (status === VoiceAssistantStatus.IDLE_LISTENING) {
      retryRef.current = 0;
      startIdleListening();
    } else {
      stopRecognition();
    }
  }, [status, startIdleListening, stopRecognition]);

  // ── Pause when tab hidden ─────────────────────────────────────────────────
  useEffect(() => {
    const onVis = () => {
      if (document.hidden) {
        stopRecognition();
      } else if (statusRef.current === VoiceAssistantStatus.IDLE_LISTENING) {
        startIdleListening();
      }
    };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, [startIdleListening, stopRecognition]);

  // ── Manual trigger ────────────────────────────────────────────────────────
  const manualTrigger = useCallback(async () => {
    const cur = statusRef.current;
    console.log('[Senorita] Manual trigger — status:', cur);

    if (cur === VoiceAssistantStatus.IDLE_LISTENING) {
      await stopRecognition();
      startRecordingCommand();
    } else if (cur === VoiceAssistantStatus.RECORDING_COMMAND) {
      if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
    } else if (cur === VoiceAssistantStatus.SPEAKING_RESPONSE || cur === VoiceAssistantStatus.GREETING) {
      cancelTTS();
      setVoiceResponse(null);
      setStatus(VoiceAssistantStatus.IDLE_LISTENING);
    }
  }, [stopRecognition, startRecordingCommand, cancelTTS]);

  // ── Time-aware page-load greeting ─────────────────────────────────────────
  const playWelcome = useCallback(async () => {
    const h = new Date().getHours();
    const period = h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';

    const lines: Record<string, string[]> = {
      morning: [
        "Good morning. Coffee or commands first? Either way, I am ready.",
        "Rise and shine. The day is yours — what are we doing today?",
        "Morning, sir. I pulled up everything. Let us make it count.",
        "Good morning. Slept well? Because I have been working all night.",
        "Morning. Your schedule is clear. Let us fill it wisely.",
        "Good morning. I am warmed up and ready whenever you are.",
      ],
      afternoon: [
        "Afternoon. Still going strong? Tell me what you need.",
        "Good afternoon. The day is half done — let us make the rest count.",
        "Hey. Right on time. What can I do for you?",
        "Good afternoon. I have been keeping things in order. Your call.",
        "Afternoon, sir. Productive morning? Let us keep that energy going.",
        "Good afternoon. I am here, focused, and ready. Go ahead.",
      ],
      evening: [
        "Good evening. Long day? Tell me about it — I am listening.",
        "Evening. You made it. What do you still need to get done?",
        "Good evening, sir. Quiet hours are the best hours. How can I help?",
        "Evening. I am here. Let us wrap things up properly.",
        "Good evening. The world slows down — but we do not have to. What is on your mind?",
        "Evening. Sit back. I have got things from here.",
      ],
    };

    const pool = lines[period];
    const text = pool[Math.floor(Math.random() * pool.length)];

    // Wait for token to be available and TTS engine to initialise
    await new Promise(r => setTimeout(r, 700));
    if (statusRef.current !== VoiceAssistantStatus.IDLE_LISTENING) return;

    setStatus(VoiceAssistantStatus.GREETING);
    setVoiceResponse(text);
    isSpeakingRef.current = true;

    await speakWithBackend(text);

    isSpeakingRef.current = false;
    setVoiceResponse(null);
    setStatus(VoiceAssistantStatus.IDLE_LISTENING);
  }, [speakWithBackend]);

  const welcomePlayedRef = useRef(false);

  // Auto-greet on first mount
  useEffect(() => {
    if (welcomePlayedRef.current) return;
    welcomePlayedRef.current = true;
    playWelcome();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      stopRecognition();
      cancelTTS();
      releaseStream();
      if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
      if (vadFrameRef.current) cancelAnimationFrame(vadFrameRef.current);
    };
  }, [stopRecognition, cancelTTS, releaseStream]);

  return { status, voiceResponse, activeStream, manualTrigger, isWakeWordEnabled, setIsWakeWordEnabled };
}
