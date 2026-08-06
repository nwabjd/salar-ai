declare module 'react-native-voice' {
  interface SpeechResultsEvent {
    value: string[];
  }
  interface SpeechErrorEvent {
    error: any;
  }
  const Voice: {
    start(locale: string): Promise<void>;
    stop(): Promise<void>;
    cancel(): Promise<void>;
    destroy(): Promise<void>;
    removeAllListeners(): void;
    onSpeechResults: ((event: SpeechResultsEvent) => void) | null;
    onSpeechEnd: (() => void) | null;
    onSpeechError: ((event: SpeechErrorEvent) => void) | null;
    onSpeechStart: (() => void) | null;
    onSpeechPartialResults: ((event: SpeechResultsEvent) => void) | null;
  };
  export default Voice;
}
