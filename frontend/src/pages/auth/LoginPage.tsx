import { useState } from 'react';
import { TextField, Button, Typography, Box, Alert } from '@mui/material';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) { setError('请填写用户名和密码'); return; }
    setLoading(true);
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(axiosErr?.response?.data?.detail || axiosErr?.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <TextField fullWidth label="用户名" size="small" value={username} onChange={(e) => setUsername(e.target.value)} sx={{ mb: 2, input: { color: '#e0e0e0' } }} />
      <TextField fullWidth label="密码" type="password" size="small" value={password} onChange={(e) => setPassword(e.target.value)} sx={{ mb: 2, input: { color: '#e0e0e0' } }} />
      <Button fullWidth type="submit" variant="contained" disabled={loading} sx={{ mb: 1.5, bgcolor: '#00d4ff', '&:hover': { bgcolor: '#00b8e6' } }}>
        {loading ? '登录中...' : '登录'}
      </Button>
      <Typography variant="body2" sx={{ textAlign: 'center', color: '#a0a0b0' }}>
        没有账号？<Link to="/register" style={{ color: '#00d4ff' }}>注册</Link>
      </Typography>
    </Box>
  );
}
