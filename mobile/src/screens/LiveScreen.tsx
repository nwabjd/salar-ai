import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Animated, Easing, BackHandler } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import Tts from 'react-native-tts';
import Voice from 'react-native-voice';
import { createAudioPlayer, AudioPlayer } from 'expo-audio';
import { createConversation, chatStream, tts as apiTts, getBaseUrl, getToken } from '../api';
import { colors } from '../theme';

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode.apply(null, chunk as any);
  }
  // RN doesn't have btoa, use a manual lookup
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let result = '';
  for (let i = 0; i < binary.length; i += 3) {
    const a = binary.charCodeAt(i);
    const b = i + 1 < binary.length ? binary.charCodeAt(i + 1) : 0;
    const c = i + 2 < binary.length ? binary.charCodeAt(i + 2) : 0;
    result += chars[(a >> 2) & 63];
    result += chars[((a & 3) << 4) | ((b >> 4) & 15)];
    result += i + 1 < binary.length ? chars[((b & 15) << 2) | ((c >> 6) & 3)] : '=';
    result += i + 2 < binary.length ? chars[c & 63] : '=';
  }
  return result;
}

type Phase = 'listening' | 'thinking' | 'speaking';

export default function LiveScreen({ connected, onClose }: { connected: boolean; onClose: () => void }) {
  const [phase, setPhase] = useState<Phase>('listening');
  const conversationId = useRef('');
  const phaseRef = useRef<Phase>('listening');
  const replyBuf = useRef('');
  const soundRef = useRef<AudioPlayer | null>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const rotateAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (phase === 'listening') {
      const loop = Animated.loop(Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.15, duration: 1200, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 1200, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]));
      loop.start();
      return () => loop.stop();
    }
  }, [phase]);

  useEffect(() => {
    if (phase === 'thinking') {
      rotateAnim.setValue(0);
      const loop = Animated.loop(Animated.timing(rotateAnim, { toValue: 1, duration: 1500, easing: Easing.linear, useNativeDriver: true }));
      loop.start();
      return () => loop.stop();
    }
  }, [phase]);

  useEffect(() => {
    if (phase === 'speaking') {
      const loop = Animated.loop(Animated.sequence([
        Animated.timing(scaleAnim, { toValue: 1.35, duration: 200, useNativeDriver: true }),
        Animated.timing(scaleAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
      ]));
      loop.start();
      return () => loop.stop();
    } else {
      scaleAnim.setValue(1);
    }
  }, [phase]);

  useEffect(() => {
    Tts.setDefaultRate(0.5, true);
    Tts.setDefaultPitch(1.0);

    Voice.onSpeechResults = (event: any) => {
      if (event.value?.[0] && phaseRef.current === 'listening') {
        sendToBackend(event.value[0].trim());
      }
    };
    Voice.onSpeechEnd = () => {
      if (phaseRef.current === 'listening') safeStartVoice();
    };
    Voice.onSpeechError = () => {
      if (phaseRef.current === 'listening') setTimeout(safeStartVoice, 500);
    };

    createConversation('Live session').then(c => { conversationId.current = c.id; });

    return () => {
      Voice.destroy().then(Voice.removeAllListeners);
      Tts.stop();
      if (soundRef.current) { soundRef.current.remove(); soundRef.current = null; }
    };
  }, []);

  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      onClose();
      return true;
    });
    return () => sub.remove();
  }, [onClose]);

  useEffect(() => {
    if (connected) safeStartVoice();
    return () => { try { Voice.stop() } catch {} };
  }, [connected]);

  function safeStartVoice() {
    try { Voice.start('en-US') } catch {}
  }

  async function sendToBackend(text: string) {
    if (!conversationId.current || phaseRef.current === 'thinking') return;
    phaseRef.current = 'thinking'; setPhase('thinking'); replyBuf.current = '';
    try { Tts.stop(); } catch {}
    try { await Voice.stop(); } catch {}

    const baseUrl = await getBaseUrl();
    const token = await getToken();

    chatStream(conversationId.current, text, baseUrl, token,
      (t) => { replyBuf.current += t; },
      async () => {
        if (!replyBuf.current) { resetToListening(); return; }
        await speakResponse(replyBuf.current);
      },
      () => { resetToListening(); }
    );
  }

  async function speakResponse(text: string) {
    try {
      phaseRef.current = 'speaking'; setPhase('speaking');
      const audioData = await apiTts(text);
      const base64 = arrayBufferToBase64(audioData);
      const uri = `data:audio/mpeg;base64,${base64}`;

      if (soundRef.current) { soundRef.current.remove(); soundRef.current = null; }
      const sound = createAudioPlayer({ uri });
      soundRef.current = sound;
      sound.play();
      sound.addListener('playbackStatusUpdate', (status: any) => {
        if (status.didJustFinish) { soundRef.current = null; resetToListening(); }
      });
    } catch {
      try {
        phaseRef.current = 'speaking'; setPhase('speaking');
        await Tts.speak(text);
      } catch {}
      resetToListening();
    }
  }

  function resetToListening() {
    phaseRef.current = 'listening'; setPhase('listening');
    setTimeout(safeStartVoice, 300);
  }

  const spin = rotateAnim.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '360deg'] });
  const orbColor = phase === 'listening' ? colors.accent : phase === 'thinking' ? colors.accentTwo : colors.green;
  const ringColor = phase === 'listening' ? 'rgba(252,66,255,0.25)' : phase === 'thinking' ? 'rgba(66,252,255,0.3)' : 'rgba(112,229,170,0.3)';

  return (
    <SafeAreaView style={s.container} edges={['top', 'bottom']}>
      <TouchableOpacity style={s.closeBtn} onPress={onClose}>
        <Ionicons name="close" size={24} color={colors.ink} />
      </TouchableOpacity>

      <View style={s.center}>
        <Animated.View style={[s.ring, s.ring3, { borderColor: ringColor, transform: [{ scale: pulseAnim }] }]} />
        <Animated.View style={[s.ring, s.ring2, { borderColor: ringColor, transform: [{ scale: phase === 'thinking' ? rotateAnim.interpolate({ inputRange: [0, 1], outputRange: [1, 1.08] }) : pulseAnim }, { rotate: phase === 'thinking' ? spin : '0deg' }] }]} />
        <Animated.View style={[s.ring, s.ring1, { borderColor: ringColor, transform: [{ scale: phase === 'speaking' ? scaleAnim : pulseAnim }] }]} />
        <Animated.View style={[s.core, { backgroundColor: orbColor, shadowColor: orbColor, transform: [{ scale: phase === 'speaking' ? scaleAnim : new Animated.Value(1) }] }]} />
      </View>

      <Text style={s.label}>
        {phase === 'listening' ? 'Listening…' : phase === 'thinking' ? 'Thinking…' : 'Speaking…'}
      </Text>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.canvasLive },
  closeBtn: { position: 'absolute', top: 16, right: 16, width: 44, height: 44, borderRadius: 14, borderWidth: 1, borderColor: colors.line, backgroundColor: 'rgba(5,4,10,0.4)', justifyContent: 'center', alignItems: 'center', zIndex: 10 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  ring: { position: 'absolute', borderRadius: 999, borderWidth: 1.5 },
  ring1: { width: 100, height: 100 },
  ring2: { width: 180, height: 180 },
  ring3: { width: 260, height: 260 },
  core: { width: 24, height: 24, borderRadius: 12, shadowOffset: { width: 0, height: 0 }, shadowOpacity: 1, shadowRadius: 30, elevation: 15 },
  label: { fontSize: 14, color: colors.muted, letterSpacing: 2, textTransform: 'uppercase', textAlign: 'center', paddingBottom: 80 },
});
