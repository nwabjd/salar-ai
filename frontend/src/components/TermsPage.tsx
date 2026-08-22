export function TermsPage({ onClose }: { onClose: () => void }) {
  return (
    <div className="terms-overlay">
      <div className="terms-content">
        <span className="eyebrow">LEGAL</span>
        <h1>Terms & Policies</h1>
        <p className="terms-subtitle">Last updated: August 2026</p>

        <div className="terms-section">
          <h2>1. Acceptance of Terms</h2>
          <p>By accessing or using Salaar ("the Service"), you agree to be bound by these Terms of Use. If you do not agree to these terms, please do not use the Service.</p>
        </div>

        <div className="terms-section">
          <h2>2. Description of Service</h2>
          <p>Salaar is a private intelligence platform that provides AI-powered assistance, memory management, knowledge organization, and device coordination. The Service is designed to operate with a focus on user privacy and data sovereignty.</p>
        </div>

        <div className="terms-section">
          <h2>3. User Accounts</h2>
          <p>You are responsible for maintaining the confidentiality of your account credentials. You agree to notify us immediately of any unauthorized use of your account. You must be at least 13 years old to use the Service.</p>
        </div>

        <div className="terms-section">
          <h2>4. Privacy & Data</h2>
          <p>Your data is stored locally on your devices by default. We do not sell or share your personal information with third parties for advertising purposes. Memory and knowledge data remain under your control. We collect minimal usage data to improve the Service.</p>
        </div>

        <div className="terms-section">
          <h2>5. Acceptable Use</h2>
          <p>You agree not to use the Service to: (a) violate any applicable laws; (b) infringe upon the rights of others; (c) transmit harmful, abusive, or illegal content; (d) attempt to gain unauthorized access to the Service or other users' accounts; (e) interfere with or disrupt the Service.</p>
        </div>

        <div className="terms-section">
          <h2>6. Intellectual Property</h2>
          <p>The Service and its original content, features, and functionality are owned by Salaar and are protected by international copyright, trademark, patent, trade secret, and other intellectual property laws.</p>
        </div>

        <div className="terms-section">
          <h2>7. Subscription & Payments</h2>
          <p>Paid subscriptions are billed in advance on a recurring basis. You may cancel your subscription at any time. Refunds are handled on a case-by-case basis. We reserve the right to modify pricing with 30 days' notice.</p>
        </div>

        <div className="terms-section">
          <h2>8. Limitation of Liability</h2>
          <p>To the maximum extent permitted by law, Salaar shall not be liable for any indirect, incidental, special, consequential, or punitive damages resulting from your use of the Service.</p>
        </div>

        <div className="terms-section">
          <h2>9. Changes to Terms</h2>
          <p>We reserve the right to modify these terms at any time. Continued use of the Service after changes constitutes acceptance of the new terms. We will notify users of material changes via email or in-app notification.</p>
        </div>

        <div className="terms-section">
          <h2>10. Contact</h2>
          <p>For questions about these Terms, please contact us at support@salaar.cloud</p>
        </div>

        <button className="terms-close" onClick={onClose}>Close</button>
      </div>
    </div>
  )
}
