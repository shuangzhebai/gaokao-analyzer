import { useState } from 'react';
import { TextField, Button, Alert, Box } from '@mui/material';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

export default function RegisterPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) { setError('请填写所有字段'); return; }
    if (password !== confirm) { setError('两次密码不一致'); return; }
    if (password.length < 6) { setError('密码至少 6 位'); return; }
    setLoading(true);
    try {
      await register(username, password);
      navigate('/login', { replace: true });
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(axiosErr?.response?.data?.detail || axiosErr?.message || '注册失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <TextField fullWidth label="用户名" size="small" value={username} onChange={(e) => setUsername(e.target.value)} sx={{ mb: 2 }} />
      <TextField fullWidth label="密码" type="password" size="small" value={password} onChange={(e) => setPassword(e.target.value)} sx={{ mb: 2 }} />
      <TextField fullWidth label="确认密码" type="password" size="small" value={confirm} onChange={(e) => setConfirm(e.target.value)} sx={{ mb: 2 }} />
      <Button fullWidth type="submit" variant="contained" disabled={loading} sx={{ mb: 1.5, bgcolor: '#00d4ff', '&:hover': { bgcolor: '#00b8e6' } }}>
        {loading ? '注册中...' : '注册'}
      </Button>
      <Box sx={{ textAlign: 'center' }}>
        <Link to="/login" style={{ color: '#00d4ff', fontSize: 14 }}>已有账号？登录</Link>
      </Box>
    </Box>
  );
}
