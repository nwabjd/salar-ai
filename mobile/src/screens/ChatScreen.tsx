import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TextInput, TouchableOpacity, FlatList, StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { conversations, createConversation, getConversation, chatStream, getBaseUrl, getToken, Message } from '../api';
import { colors } from '../theme';

type Props = { connected: boolean; onOpenSettings: () => void; onOpenLive: () => void };

export default function ChatScreen({ connected, onOpenSettings, onOpenLive }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [streaming, setStreaming] = useState('');
  const [conversationId, setConversationId] = useState('');
  const streamBuf = useRef('');
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    if (!connected) return;
    conversations().then(async list => {
      const item = list[0] || await createConversation();
      setConversationId(item.id);
      if (list[0]) {
        const detail = await getConversation(item.id);
        setMessages(detail.messages || []);
      }
    }).catch(() => {});
  }, [connected]);

  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => flatListRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [messages, streaming]);

  async function send() {
    if (!input.trim() || !conversationId || busy) return;
    const content = input; setInput(''); setBusy(true); setStreaming(''); streamBuf.current = '';
    const userMsg: Message = { id: 'tmp-' + Date.now(), role: 'user', content, created_at: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);

    const baseUrl = await getBaseUrl();
    const token = await getToken();

    chatStream(conversationId, content, baseUrl, token,
      (token) => { streamBuf.current += token; setStreaming(streamBuf.current); },
      (messageId, createdAt) => {
        setMessages(prev => [...prev.slice(0, -1), userMsg, { id: messageId, role: 'assistant', content: streamBuf.current, created_at: createdAt }]);
        setStreaming(''); streamBuf.current = ''; setBusy(false);
      },
      () => { setStreaming(''); streamBuf.current = ''; setBusy(false); }
    );
  }

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.topbar}>
        <Text style={s.brand}>SALAR</Text>
        <View style={s.topActions}>
          <TouchableOpacity style={s.iconBtn} onPress={onOpenLive}>
            <Ionicons name="mic" size={20} color={colors.accent} />
          </TouchableOpacity>
          <TouchableOpacity style={s.iconBtn} onPress={onOpenSettings}>
            <Ionicons name="settings-outline" size={20} color={colors.muted} />
          </TouchableOpacity>
        </View>
      </View>

      {messages.length === 0 && !streaming && (
        <View style={s.hero}>
          <Text style={s.heroEyebrow}>COORDINATED INTELLIGENCE</Text>
          <Text style={s.heroTitle}>What shall{'\n'}we accomplish?</Text>
          <Text style={s.heroSub}>Private intelligence, memory, and your connected devices—coordinated from one place.</Text>
        </View>
      )}

      <FlatList
        ref={flatListRef}
        style={s.list}
        contentContainerStyle={s.listContent}
        data={messages}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <View style={[s.msg, item.role === 'user' ? s.msgUser : s.msgAssistant]}>
            <Text style={s.msgLabel}>{item.role === 'assistant' ? 'SALAR' : 'YOU'}</Text>
            <Text style={[s.msgText, item.role === 'user' && s.msgTextUser]}>{item.content}</Text>
          </View>
        )}
      />

      {streaming ? (
        <View style={[s.msg, s.msgAssistant]}>
          <Text style={s.msgLabel}>SALAR</Text>
          <Text style={s.msgText}>{streaming}</Text>
        </View>
      ) : null}

      {busy && !streaming ? (
        <View style={[s.msg, s.msgAssistant]}>
          <Text style={s.msgLabel}>SALAR</Text>
          <ActivityIndicator size="small" color={colors.accent} style={{ marginTop: 8 }} />
        </View>
      ) : null}

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={0}>
        <View style={s.composer}>
          <TextInput
            style={s.composerInput}
            value={input}
            onChangeText={setInput}
            onSubmitEditing={send}
            placeholder="Ask anything…"
            placeholderTextColor={colors.muted}
            returnKeyType="send"
            editable={connected && !busy}
          />
          <TouchableOpacity style={[s.sendBtn, (!connected || busy || !input.trim()) && s.sendDisabled]} onPress={send} disabled={!connected || busy || !input.trim()}>
            <Ionicons name="arrow-up" size={20} color="#fff" />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.canvas },
  topbar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 12 },
  brand: { fontSize: 13, fontWeight: '600', color: colors.ink, letterSpacing: 3 },
  topActions: { flexDirection: 'row', gap: 8 },
  iconBtn: { width: 40, height: 40, borderRadius: 12, borderWidth: 1, borderColor: colors.line, backgroundColor: 'rgba(255,255,255,0.03)', justifyContent: 'center', alignItems: 'center' },
  hero: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 32 },
  heroEyebrow: { fontSize: 9, color: colors.muted, letterSpacing: 2.5, textTransform: 'uppercase', marginBottom: 12 },
  heroTitle: { fontSize: 36, fontWeight: '300', color: colors.ink, textAlign: 'center', lineHeight: 42, letterSpacing: -1 },
  heroSub: { fontSize: 13, color: colors.muted, textAlign: 'center', marginTop: 12, lineHeight: 20 },
  list: { flex: 1 },
  listContent: { padding: 20, paddingBottom: 8 },
  msg: { marginBottom: 16, maxWidth: '85%' },
  msgUser: { alignSelf: 'flex-end', alignItems: 'flex-end' },
  msgAssistant: { alignSelf: 'flex-start' },
  msgLabel: { fontSize: 9, color: colors.muted, letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 4 },
  msgText: { fontSize: 15, color: colors.ink, lineHeight: 22, backgroundColor: colors.cardBg, padding: 14, borderRadius: 16, borderBottomLeftRadius: 4, borderWidth: 1, borderColor: colors.line },
  msgTextUser: { backgroundColor: 'rgba(252,66,255,0.1)', borderBottomRightRadius: 4, borderBottomLeftRadius: 16, borderColor: 'rgba(252,66,255,0.15)' },
  composer: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingBottom: 12, paddingTop: 4, gap: 8 },
  composerInput: { flex: 1, backgroundColor: colors.inputBg, borderWidth: 1, borderColor: colors.line, borderRadius: 14, padding: 14, color: colors.ink, fontSize: 15 },
  sendBtn: { width: 44, height: 44, borderRadius: 14, backgroundColor: colors.accent, justifyContent: 'center', alignItems: 'center' },
  sendDisabled: { opacity: 0.3 },
});
