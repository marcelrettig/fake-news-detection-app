// src/pages/Login.jsx
import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { auth } from '../firebase';
import { signInWithEmailAndPassword } from 'firebase/auth';
import {
  Container,
  Box,
  Typography,
  TextField,
  Button,
  Snackbar,
  Alert,
  Paper
} from '@mui/material';

export default function Login() {
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [loading, setLoading] = useState(false);

  // snackbar state
  const [snack, setSnack] = useState({ open: false, message: '', severity: 'info' });

  const location = useLocation();
  const navigate = useNavigate();
  const from = location.state?.from?.pathname || '/';

  const handleClose = () => setSnack(s => ({ ...s, open: false }));

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await signInWithEmailAndPassword(auth, email, pw);
      setSnack({ open: true, message: 'Successfully signed in!', severity: 'success' });
      // give user a moment to see the message
      setTimeout(() => navigate(from, { replace: true }), 500);
    } catch (err) {
      console.error(err);
      setSnack({ open: true, message: 'Login failed: ' + (err.code || err.message), severity: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="xs">
      <Paper elevation={3} sx={{ mt: 8, p: 4 }}>
        <Box textAlign="center" mb={2}>
          <Typography variant="h5">Sign In</Typography>
        </Box>

        <Box component="form" onSubmit={submit} noValidate>
          <TextField
            label="Email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            fullWidth
            margin="normal"
          />

          <TextField
            label="Password"
            type="password"
            value={pw}
            onChange={e => setPw(e.target.value)}
            required
            fullWidth
            margin="normal"
          />

          <Button
            type="submit"
            variant="contained"
            color="primary"
            fullWidth
            disabled={loading || !email || !pw}
            sx={{ mt: 2 }}
          >
            {loading ? 'Signing In…' : 'Sign In'}
          </Button>
        </Box>
      </Paper>

      <Snackbar
        open={snack.open}
        autoHideDuration={4000}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleClose} severity={snack.severity} sx={{ width: '100%' }}>
          {snack.message}
        </Alert>
      </Snackbar>
    </Container>
  );
}
