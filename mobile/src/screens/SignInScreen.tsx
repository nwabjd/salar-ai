import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { sendOtp, verifyOtp } from '../auth';
import { colors } from '../theme';

export default function SignInScreen({ onConnected }: { onConnected: () => void }) {
  const [step, setStep] = useState<'email' | 'otp'>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function handleSendCode() {
    if (!/^\S+@\S+\.\S+$/.test(email)) { setError('Enter a valid email address.'); return; }
    setLoading(true); setError(''); setMessage('');
    try {
      await sendOtp(email);
      setStep('otp');
      setMessage(`A six-digit code was sent to ${email}.`);
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }

  async function handleVerify() {
    if (otp.length !== 6) { setError('Enter the complete six-digit code.'); return; }
    setLoading(true); setError('');
    try {
      await verifyOtp(email, otp);
      onConnected();
    } catch (e: any) { setError(e.message); }
    setLoading(false);
  }

  return (
    <SafeAreaView style={s.container}>
      <KeyboardAvoidingView style={s.inner} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={s.logoContainer}>
          <View style={s.logo}>
            <Ionicons name="chatbubble-ellipses" size={32} color={colors.accent} />
          </View>
          <Text style={s.title}>SALAR</Text>
          <Text style={s.subtitle}>Personal Intelligence</Text>
        </View>

        <View style={s.card}>
          {step === 'email' ? (
            <>
              <Text style={s.label}>Email</Text>
              <TextInput
                style={s.input}
                value={email}
                onChangeText={setEmail}
                placeholder="you@example.com"
                placeholderTextColor={colors.muted}
                autoCapitalize="none"
                keyboardType="email-address"
                autoFocus
              />
              <TouchableOpacity style={[s.btn, loading && s.btnDisabled]} onPress={handleSendCode} disabled={loading || !email}>
                {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Send my code</Text>}
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={s.label}>Verification code</Text>
              <TextInput
                style={s.input}
                value={otp}
                onChangeText={setOtp}
                placeholder="123456"
                placeholderTextColor={colors.muted}
                keyboardType="number-pad"
                maxLength={6}
                autoFocus
              />
              {message ? <Text style={s.message}>{message}</Text> : null}
              <TouchableOpacity style={[s.btn, loading && s.btnDisabled]} onPress={handleVerify} disabled={loading || otp.length !== 6}>
                {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Verify and continue</Text>}
              </TouchableOpacity>
              <TouchableOpacity style={s.switchBtn} onPress={() => { setStep('email'); setMessage(''); setError(''); }}>
                <Text style={s.switchText}>Change email</Text>
              </TouchableOpacity>
            </>
          )}
          <Text style={s.hint}>No password to remember. We email you a secure six-digit sign-in code.</Text>
          {error ? <Text style={s.error}>{error}</Text> : null}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.canvas },
  inner: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  logoContainer: { alignItems: 'center', marginBottom: 48 },
  logo: { width: 72, height: 72, borderRadius: 22, borderWidth: 1, borderColor: colors.lineBright, backgroundColor: 'rgba(252,66,255,0.08)', justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  title: { fontSize: 28, fontWeight: '300', color: colors.ink, letterSpacing: -0.5 },
  subtitle: { fontSize: 11, color: colors.muted, letterSpacing: 3, textTransform: 'uppercase', marginTop: 4 },
  card: { width: '100%', maxWidth: 360, backgroundColor: colors.cardBg, borderRadius: 20, padding: 24, borderWidth: 1, borderColor: colors.line },
  label: { fontSize: 10, color: colors.muted, letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 8, marginTop: 12 },
  input: { backgroundColor: colors.inputBg, borderWidth: 1, borderColor: colors.line, borderRadius: 12, padding: 14, color: colors.ink, fontSize: 16, marginBottom: 4 },
  btn: { backgroundColor: colors.accent, borderRadius: 12, padding: 16, alignItems: 'center', marginTop: 16 },
  btnDisabled: { opacity: 0.5 },
  btnText: { color: '#fff', fontWeight: '600', fontSize: 14 },
  switchBtn: { alignItems: 'center', marginTop: 16 },
  switchText: { color: colors.muted, fontSize: 13 },
  hint: { fontSize: 12, color: colors.muted, textAlign: 'center', marginTop: 16, lineHeight: 18 },
  message: { fontSize: 13, color: colors.accentTwo, textAlign: 'center', marginTop: 12 },
  error: { color: colors.danger, fontSize: 13, textAlign: 'center', marginTop: 12 },
});
