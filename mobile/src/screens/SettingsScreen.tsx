import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { currentEmail, signOut } from '../auth';
import { colors } from '../theme';

export default function SettingsScreen({ onBack, onLogout }: { onBack: () => void; onLogout: () => void }) {
  const [email, setEmail] = useState('');

  useEffect(() => { currentEmail().then((value) => setEmail(value ?? '')); }, []);

  async function handleLogout() {
    Alert.alert('Sign out', 'This will sign you out of SALAR on this device.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign out', style: 'destructive', onPress: async () => { await signOut(); onLogout(); } },
    ]);
  }

  return (
    <SafeAreaView style={s.container}>
      <View style={s.topbar}>
        <TouchableOpacity onPress={onBack} style={s.backBtn}>
          <Ionicons name="chevron-back" size={20} color={colors.ink} />
        </TouchableOpacity>
        <Text style={s.title}>Settings</Text>
        <View style={{ width: 40 }} />
      </View>

      <View style={s.content}>
        <Text style={s.label}>Account</Text>
        <View style={s.accountRow}>
          <Ionicons name="mail-outline" size={18} color={colors.accent} />
          <Text style={s.email}>{email || 'Signed in'}</Text>
        </View>

        <View style={s.divider} />

        <TouchableOpacity style={s.logoutBtn} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={18} color={colors.danger} />
          <Text style={s.logoutText}>Sign out</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.canvas },
  topbar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 12, borderWidth: 1, borderColor: colors.line, justifyContent: 'center', alignItems: 'center' },
  title: { fontSize: 13, fontWeight: '600', color: colors.ink, letterSpacing: 2 },
  content: { flex: 1, padding: 24 },
  label: { fontSize: 10, color: colors.muted, letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 8, marginTop: 16 },
  accountRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.inputBg },
  email: { color: colors.ink, fontSize: 15, flex: 1 },
  divider: { height: 1, backgroundColor: colors.line, marginVertical: 32 },
  logoutBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: 'rgba(255,77,106,0.2)', backgroundColor: 'rgba(255,77,106,0.06)' },
  logoutText: { color: colors.danger, fontWeight: '500', fontSize: 14 },
});
