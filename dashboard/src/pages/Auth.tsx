import React, { useState } from 'react';
import { Mail, Lock, User as UserIcon, CheckCircle2, ArrowRight, Sparkles, Flame, ShieldAlert, Globe } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const API = import.meta.env.VITE_API_URL || "";

const STYLES = `
  @keyframes auth-fadeUp {
    from { opacity: 0; transform: translateY(40px) scale(0.95); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes spin3d {
    0% { transform: rotateX(0deg) rotateY(0deg); }
    100% { transform: rotateX(360deg) rotateY(360deg); }
  }
  @keyframes float {
    0%, 100% { transform: translateY(0px) rotate(0deg); }
    50% { transform: translateY(-15px) rotate(3deg); }
  }
  @keyframes pulse-glow {
    0%, 100% { opacity: 0.6; filter: drop-shadow(0 0 15px rgba(99,102,241,0.4)); }
    50% { opacity: 0.9; filter: drop-shadow(0 0 30px rgba(167,139,250,0.8)); }
  }
  @keyframes bg-shift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
  }
  @keyframes orb-move-1 {
    0%, 100% { transform: translate(0px, 0px) scale(1); }
    33% { transform: translate(30px, -50px) scale(1.1); }
    66% { transform: translate(-20px, 20px) scale(0.95); }
  }
  @keyframes orb-move-2 {
    0%, 100% { transform: translate(0px, 0px) scale(1); }
    50% { transform: translate(-40px, 40px) scale(1.15); }
  }
  
  .auth-fade-in {
    animation: auth-fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  
  .auth-gradient-text {
    background: linear-gradient(270deg, #A78BFA, #60A5FA, #34D399, #A78BFA);
    background-size: 300% 300%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: bg-shift 6s ease infinite;
  }
  
  .auth-glass-card {
    background: rgba(15, 23, 42, 0.45);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 
                inset 0 0 24px rgba(255, 255, 255, 0.02);
    transition: all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  }
  
  .auth-glass-card:hover {
    border-color: rgba(167, 139, 250, 0.3);
    box-shadow: 0 35px 60px -12px rgba(0, 0, 0, 0.6), 
                0 0 40px rgba(99, 102, 241, 0.15),
                inset 0 0 24px rgba(255, 255, 255, 0.03);
    transform: translateY(-4px) scale(1.01);
  }
  
  .auth-input-container {
    position: relative;
    transition: all 0.3s ease;
  }
  
  .auth-input {
    background: rgba(30, 41, 59, 0.45) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    backdrop-filter: blur(8px);
    transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  }
  
  .auth-input:focus {
    border-color: rgba(167, 139, 250, 0.6) !important;
    box-shadow: 0 0 15px rgba(167, 139, 250, 0.25), 
                inset 0 0 10px rgba(167, 139, 250, 0.05) !important;
    background: rgba(30, 41, 59, 0.6) !important;
  }
  
  .auth-btn {
    background: linear-gradient(135deg, #6366F1 0%, #A78BFA 50%, #EC4899 100%);
    background-size: 200% auto;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.35);
  }
  
  .auth-btn:hover:not(:disabled) {
    background-position: right center;
    box-shadow: 0 8px 30px rgba(167, 139, 250, 0.55);
    transform: translateY(-2px);
  }
  
  .auth-btn:active:not(:disabled) {
    transform: translateY(0);
  }
`;

function CubeWidget() {
  const faces = [
    { t: "rotateY(0deg) translateZ(20px)" },
    { t: "rotateY(90deg) translateZ(20px)" },
    { t: "rotateY(180deg) translateZ(20px)" },
    { t: "rotateY(270deg) translateZ(20px)" },
    { t: "rotateX(90deg) translateZ(20px)" },
    { t: "rotateX(-90deg) translateZ(20px)" },
  ];
  return (
    <div style={{ perspective: 800, animation: "float 6s ease-in-out infinite" }} className="flex justify-center my-5">
      <div style={{ width: 70, height: 70, position: "relative", transformStyle: "preserve-3d", animation: "spin3d 12s linear infinite" }}>
        {faces.map((f, i) => (
          <div key={i} style={{
            position: "absolute", 
            width: 40, height: 40,
            left: 15, top: 15,
            background: "rgba(167,139,250,0.03)", border: "1px solid rgba(167,139,250,0.25)",
            backdropFilter: "blur(4px)", transform: f.t, boxShadow: "inset 0 0 15px rgba(167,139,250,0.08)"
          }} />
        ))}
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
           <Sparkles className="text-[#A78BFA]" size={16} style={{ animation: 'pulse-glow 2s infinite' }} />
        </div>
      </div>
    </div>
  );
}

export default function Auth() {
  const [view, setView] = useState<'login' | 'signup' | 'verify'>('login');
  
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const navigate = useNavigate();

  // Handle Signup
  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    
    try {
      const res = await fetch(`${API}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: fullName, email, password })
      });
      const data = await res.json();
      
      if (!res.ok) throw new Error(data.detail || "Signup failed");
      
      setView('verify');
      setSuccess("Verification code sent to your email!");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Verify
  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    const code = otp.join('');
    
    try {
      const res = await fetch(`${API}/api/auth/verify-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, code })
      });
      const data = await res.json();
      
      if (!res.ok) throw new Error(data.detail || "Verification failed");
      
      setSuccess("Email verified! You can now log in.");
      setView('login');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Login
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    
    try {
      const res = await fetch(`${API}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      
      if (!res.ok) throw new Error(data.detail || "Login failed");
      
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user_name', data.full_name);
      
      navigate('/accueil');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    if (value.length > 1) value = value.slice(-1);
    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    if (value && index < 5) {
      const nextInput = document.getElementById(`otp-${index + 1}`);
      nextInput?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      const prevInput = document.getElementById(`otp-${index - 1}`);
      prevInput?.focus();
    }
  };

  return (
    <div 
      className="min-h-screen flex items-center justify-center p-4 overflow-hidden relative" 
      style={{ background: "#020617", fontFamily: "'DM Sans', sans-serif" }}
    >
      <style>{STYLES}</style>

      {/* Modern cyber fluid gradient base */}
      <div style={{
        position: "absolute",
        top: 0, left: 0, right: 0, bottom: 0,
        background: "radial-gradient(circle at 20% 30%, #1e1b4b 0%, #090514 50%, #020617 100%)",
        zIndex: 0
      }} />

      {/* Glowing Neon Orbs that move in background */}
      <div style={{
        position: "absolute",
        width: "500px", height: "500px",
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(99,102,241,0.15) 0%, rgba(99,102,241,0) 70%)",
        top: "10%", left: "10%",
        animation: "orb-move-1 25s infinite ease-in-out",
        filter: "blur(60px)",
        zIndex: 0
      }} />
      <div style={{
        position: "absolute",
        width: "450px", height: "450px",
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(236,72,153,0.12) 0%, rgba(236,72,153,0) 70%)",
        bottom: "10%", right: "10%",
        animation: "orb-move-2 20s infinite ease-in-out",
        filter: "blur(60px)",
        zIndex: 0
      }} />

      {/* Interactive 3D grid layout effect */}
      <div style={{
        position: "absolute",
        top: 0, left: 0, right: 0, bottom: 0,
        backgroundImage: "linear-gradient(to right, rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.02) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
        maskImage: "radial-gradient(ellipse at center, black, transparent 80%)",
        WebkitMaskImage: "radial-gradient(ellipse at center, black, transparent 80%)",
        zIndex: 0
      }} />

      <div className="w-full max-w-lg relative z-10 auth-fade-in">
        
        <div className="auth-glass-card rounded-3xl overflow-hidden p-8 md:p-10 relative">
          
          {/* Animated colorful top border */}
          <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>
          
          <div className="text-center mb-6">
            <div className="flex justify-center items-center gap-2 mb-3">
              <Sparkles className="text-indigo-400" size={20} />
              <span className="text-xs font-semibold text-indigo-300 tracking-widest uppercase">Prospect & Opportunity System</span>
            </div>
            
            {/* Elegant glass 3D Cube from AI Analyste */}
            <CubeWidget />

            <h1 className="text-3xl font-extrabold tracking-tight text-white mb-2 leading-none">
              <span className="auth-gradient-text">Opportunities / Prospection</span>
            </h1>
            <p className="text-[#94A3B8] text-sm font-medium tracking-wide">Real-Time Market View & Tracking Hub</p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-400 text-sm flex items-center gap-3">
              <ShieldAlert size={18} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="mb-6 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl text-emerald-400 text-sm flex items-center gap-3">
              <CheckCircle2 size={18} className="flex-shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {view === 'login' && (
            <form onSubmit={handleLogin} className="space-y-6">
              <h2 className="text-lg font-semibold text-white tracking-wide border-b border-slate-800 pb-2">Welcome Back</h2>
              
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Email Address</label>
                <div className="auth-input-container">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Mail size={16} className="text-slate-500" />
                  </div>
                  <input 
                    type="email" 
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="auth-input w-full pl-11 pr-4 py-3 rounded-2xl text-white placeholder-slate-500 focus:outline-none"
                    placeholder="name@teamwill.com"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Password</label>
                <div className="auth-input-container">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Lock size={16} className="text-slate-500" />
                  </div>
                  <input 
                    type="password" 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="auth-input w-full pl-11 pr-4 py-3 rounded-2xl text-white placeholder-slate-500 focus:outline-none"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <button 
                type="submit" 
                disabled={isLoading}
                className="auth-btn w-full flex items-center justify-center gap-2 py-3.5 px-4 text-white rounded-2xl font-bold tracking-wide disabled:opacity-50"
              >
                {isLoading ? 'Decrypting Space...' : 'Access Dashboard'} <ArrowRight size={18} />
              </button>

              <div className="text-center text-sm text-[#94A3B8] pt-4 border-t border-slate-800">
                New to the platform?{' '}
                <button type="button" onClick={() => setView('signup')} className="text-indigo-400 hover:text-indigo-300 font-semibold transition-colors">Create Space Account</button>
              </div>
            </form>
          )}

          {view === 'signup' && (
            <form onSubmit={handleSignup} className="space-y-6">
              <h2 className="text-lg font-semibold text-white tracking-wide border-b border-slate-800 pb-2">Establish Account</h2>
              
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Full Name</label>
                <div className="auth-input-container">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <UserIcon size={16} className="text-slate-500" />
                  </div>
                  <input 
                    type="text" 
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    required
                    className="auth-input w-full pl-11 pr-4 py-3 rounded-2xl text-white placeholder-slate-500 focus:outline-none"
                    placeholder="John Doe"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Email Address</label>
                <div className="auth-input-container">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Mail size={16} className="text-slate-500" />
                  </div>
                  <input 
                    type="email" 
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="auth-input w-full pl-11 pr-4 py-3 rounded-2xl text-white placeholder-slate-500 focus:outline-none"
                    placeholder="name@teamwill.com"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Password</label>
                <div className="auth-input-container">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Lock size={16} className="text-slate-500" />
                  </div>
                  <input 
                    type="password" 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className="auth-input w-full pl-11 pr-4 py-3 rounded-2xl text-white placeholder-slate-500 focus:outline-none"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <button 
                type="submit" 
                disabled={isLoading}
                className="auth-btn w-full flex items-center justify-center gap-2 py-3.5 px-4 text-white rounded-2xl font-bold tracking-wide disabled:opacity-50"
              >
                {isLoading ? 'Provisioning...' : 'Register Space'} <ArrowRight size={18} />
              </button>

              <div className="text-center text-sm text-[#94A3B8] pt-4 border-t border-slate-800">
                Already registered?{' '}
                <button type="button" onClick={() => setView('login')} className="text-indigo-400 hover:text-indigo-300 font-semibold transition-colors">Sign In</button>
              </div>
            </form>
          )}

          {view === 'verify' && (
            <form onSubmit={handleVerify} className="space-y-6">
              <div className="flex justify-center items-center gap-2 mb-2">
                <Globe className="text-indigo-400 animate-spin" style={{ animationDuration: '6s' }} size={24} />
                <h2 className="text-lg font-semibold text-white tracking-wide">Verification Shield</h2>
              </div>
              <p className="text-sm text-slate-400 text-center mb-6 leading-relaxed">
                A 6-digit cryptographic verification code has been dispatched to <strong className="text-white">{email}</strong>. Please confirm ownership below.
              </p>
              
              <div className="flex justify-between gap-2 max-w-xs mx-auto mb-6">
                {otp.map((digit, i) => (
                  <input
                    key={i}
                    id={`otp-${i}`}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleOtpChange(i, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(i, e)}
                    className="w-11 h-14 text-center text-2xl font-bold bg-slate-900/80 border border-slate-700/80 rounded-2xl text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                  />
                ))}
              </div>

              <button 
                type="submit" 
                disabled={isLoading || otp.some(d => !d)}
                className="auth-btn w-full flex items-center justify-center gap-2 py-3.5 px-4 text-white rounded-2xl font-bold tracking-wide disabled:opacity-50"
              >
                {isLoading ? 'Verifying Code...' : 'Unlock Portal'} <CheckCircle2 size={18} />
              </button>
            </form>
          )}

        </div>
      </div>
    </div>
  );
}
