import { supabase } from './supabase';
import { supabaseLogin as bridgeToBackend, clearToken } from './api';

export async function sendOtp(email: string) {
  const { error } = await supabase.auth.signInWithOtp({ email, options: { shouldCreateUser: true } });
  if (error) throw error;
}

export async function verifyOtp(email: string, token: string) {
  const { data, error } = await supabase.auth.verifyOtp({ email, token, type: 'email' });
  if (error) throw error;
  if (!data.session?.access_token) throw new Error('No session returned from Supabase');
  await bridgeToBackend(data.session.access_token);
}

export async function recoverSession(): Promise<boolean> {
  const { data } = await supabase.auth.getSession();
  const session = data.session;
  if (!session?.access_token) return false;
  try {
    await bridgeToBackend(session.access_token);
    return true;
  } catch {
    return false;
  }
}

export async function signOut() {
  await supabase.auth.signOut();
  await clearToken();
}

export async function currentEmail(): Promise<string | null> {
  const { data } = await supabase.auth.getUser();
  return data.user?.email ?? null;
}
