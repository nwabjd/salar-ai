import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, MessageSquare, Plus, Send, Mic2, Paperclip, FileText, PenLine, X } from 'lucide-react';
import './design/global.css';

// Minimalist animated UI for MoonLink preview
export default function PreviewApp() {
  const [messages, setMessages] = useState<{role: 'user'|'assistant', content: string}[]>([
    { role: 'assistant', content: 'Welcome to MoonLink IT. I am ready to help you find the perfect components.' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages(prev => [...prev, { role: 'user', content: input }]);
    setInput('');
    setIsTyping(true);
    setTimeout(() => {
        setIsTyping(false);
        setMessages(prev => [...prev, { role: 'assistant', content: 'Scanning MoonLink inventory for top-tier RAM and SSDs. I found several high-performance options for your laptop.' }]);
    }, 1500);
  };

  return (
    <div className="companion-shell">
      <nav className="primary-nav--rail">
        <div className="primary-nav__brand">ML</div>
      </nav>
      <main className="companion-shell__canvas">
        <div className="companion-shell__content">
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>MoonLink IT</motion.h1>
          <div className="conversation-messages">
            {messages.map((m, i) => (
              <motion.div key={i} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className={`conversation-message conversation-message--${m.role}`}>
                <p>{m.content}</p>
              </motion.div>
            ))}
            {isTyping && <div className="skeleton" style={{width: '200px', height: '40px'}} />}
          </div>
          
          <div className="conversation-composer">
            <textarea value={input} onChange={e => setInput(e.target.value)} placeholder="Ask about RAM, SSDs, or Laptops..." />
            <div className="conversation-composer__actions">
                <button><Paperclip size={16}/> Attach</button>
                <button><PenLine size={16}/> Sign</button>
                <button className="conversation-composer__send" onClick={handleSend}><Send size={16}/> Send</button>
            </div>
          </div>
        </div>
      </main>
      <div className="context-drawer">
         <h2>AI Agent Hub</h2>
         <p>NIM Routing Active</p>
         <div className="conversation-inspector__tool">
            <span>Selected Model</span>
            <pre>poolside/laguna-xs-2.1</pre>
         </div>
      </div>
    </div>
  );
}
