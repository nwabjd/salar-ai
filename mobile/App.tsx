import React, { useState, useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import ChatScreen from './src/screens/ChatScreen';
import LiveScreen from './src/screens/LiveScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import SignInScreen from './src/screens/SignInScreen';
import { validateSession } from './src/api';
import { recoverSession, signOut } from './src/auth';
import { colors } from './src/theme';

type Screen = 'signin' | 'chat' | 'live' | 'settings';

export default function App() {
  const [screen, setScreen] = useState<Screen>('signin');
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        await validateSession();
        setConnected(true); setScreen('chat');
      } catch {
        const recovered = await recoverSession();
        if (recovered) { setConnected(true); setScreen('chat'); }
      }
    })();
  }, []);

  if (screen === 'signin') {
    return (
      <SafeAreaProvider>
        <StatusBar style="light" />
        <SignInScreen onConnected={() => { setConnected(true); setScreen('chat'); }} />
      </SafeAreaProvider>
    );
  }

  if (screen === 'settings') {
    return (
      <SafeAreaProvider>
        <StatusBar style="light" />
        <SettingsScreen
          onBack={() => setScreen('chat')}
          onLogout={async () => { await signOut(); setConnected(false); setScreen('signin'); }}
        />
      </SafeAreaProvider>
    );
  }

  if (screen === 'live') {
    return (
      <SafeAreaProvider>
        <StatusBar style="light" />
        <LiveScreen connected={connected} onClose={() => setScreen('chat')} />
      </SafeAreaProvider>
    );
  }

  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <ChatScreen
        connected={connected}
        onOpenSettings={() => setScreen('settings')}
        onOpenLive={() => setScreen('live')}
      />
    </SafeAreaProvider>
  );
}
