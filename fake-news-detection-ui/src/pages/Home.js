import React, { useState, useEffect } from 'react';
import { auth } from '../firebase';                      // your Firebase init
import { onAuthStateChanged } from 'firebase/auth';
import {
  Container,
  Box,
  Typography,
  Paper,
  TextField,
  Button,
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Divider,
  List,
  ListItem,
  ListItemText,
  CircularProgress
} from '@mui/material';

const Home = () => {
  // form state
  const [postText, setPostText] = useState('');
  const [useExternalInfo, setUseExternalInfo] = useState(true);
  const [promptVariant, setPromptVariant] = useState('default');
  const [outputType, setOutputType] = useState('score');
  const [iterations, setIterations] = useState(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // auth state
  const [token, setToken] = useState('');
  const [authChecked, setAuthChecked] = useState(false);

  // listen for Firebase auth state
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (user) => {
      if (user) {
        const tk = await user.getIdToken(true);
        setToken(tk);
      } else {
        setToken('');
      }
      setAuthChecked(true);
    });
    return () => unsub();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!postText.trim() || !token) return;
    setLoading(true);
    setResult(null);

    const payload = {
      post: postText,
      use_external_info: useExternalInfo,
      prompt_variant: promptVariant,
      output_type: outputType,
      iterations: iterations
    };

    try {
      const response = await fetch('http://localhost:8000/classify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error(response.statusText);
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error('Error:', error);
      setResult({ error: 'An error occurred while classifying the post.' });
    } finally {
      setLoading(false);
    }
  };

  const renderResponses = () => {
    if (!result) return null;
    const responses = Array.isArray(result.responses)
      ? result.responses
      : [result.truthfulness];

    return (
      <List dense>
        {responses.map((resp, idx) => (
          <ListItem key={idx} alignItems="flex-start">
            <ListItemText
              primary={<Typography variant="body2"><strong>Run {idx + 1}:</strong></Typography>}
              secondary={
                <Typography component="pre" variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {resp}
                </Typography>
              }
            />
          </ListItem>
        ))}
      </List>
    );
  };

  // Show loading while we wait for auth
  if (!authChecked) {
    return (
      <Container>
        <Box textAlign="center" mt={10}>
          <CircularProgress />
          <Typography>Checking authentication…</Typography>
        </Box>
      </Container>
    );
  }

  // If not signed in, block access
  if (!token) {
    return (
      <Container>
        <Box textAlign="center" mt={10}>
          <Typography color="error">
            You must be signed in to access this page.
          </Typography>
        </Box>
      </Container>
    );
  }

  // Authenticated UI
  return (
    <Container maxWidth="sm">
      <Box my={4}>
        <Typography variant="h4" align="center" gutterBottom>
          Fake News Classifier
        </Typography>

        <Paper elevation={3} sx={{ p: 3, mb: 4 }}>
          <form onSubmit={handleSubmit}>
            <TextField
              label="Social Media Post"
              multiline
              rows={4}
              fullWidth
              value={postText}
              onChange={(e) => setPostText(e.target.value)}
              margin="normal"
            />

            <Box display="flex" flexWrap="wrap" gap={2} my={2}>
              <FormControlLabel
                control={
                  <Switch
                    checked={useExternalInfo}
                    onChange={(e) => setUseExternalInfo(e.target.checked)}
                  />
                }
                label="Use External Info"
              />

              <FormControl sx={{ minWidth: 140 }} size="small">
                <InputLabel>Prompt Variant</InputLabel>
                <Select
                  value={promptVariant}
                  label="Prompt Variant"
                  onChange={(e) => setPromptVariant(e.target.value)}
                >
                  <MenuItem value="default">Default</MenuItem>
                  <MenuItem value="short">Short</MenuItem>
                </Select>
              </FormControl>

              <FormControl sx={{ minWidth: 140 }} size="small">
                <InputLabel>Output Type</InputLabel>
                <Select
                  value={outputType}
                  label="Output Type"
                  onChange={(e) => setOutputType(e.target.value)}
                >
                  <MenuItem value="score">Score</MenuItem>
                  <MenuItem value="binary">Binary</MenuItem>
                  <MenuItem value="detailed">Detailed</MenuItem>
                </Select>
              </FormControl>

              <TextField
                label="Iterations"
                type="number"
                InputProps={{ inputProps: { min: 1 } }}
                value={iterations}
                onChange={(e) =>
                  setIterations(Math.max(1, parseInt(e.target.value) || 1))
                }
                size="small"
                sx={{ width: 100 }}
              />
            </Box>

            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={loading}
              fullWidth
            >
              {loading ? 'Classifying...' : 'Classify'}
            </Button>
          </form>
        </Paper>

        {result && (
          <Card variant="outlined" sx={{ mb: 4 }}>
            <CardContent>
              {result.error ? (
                <Typography color="error" align="center">
                  {result.error}
                </Typography>
              ) : (
                <>
                  <Typography variant="h6" gutterBottom>
                    Results
                  </Typography>

                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2">Parameters</Typography>
                    <Typography variant="body2">
                      External Info: <strong>{result.external_info_used ? 'Yes' : 'No'}</strong><br />
                      Prompt Variant: <strong>{result.used_prompt_variant}</strong><br />
                      Output Type: <strong>{result.output_type}</strong><br />
                      Iterations: <strong>{result.iterations || 1}</strong>
                    </Typography>
                  </Box>

                  <Divider sx={{ my: 2 }} />

                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2">Search Query</Typography>
                    <Typography variant="body1" sx={{ wordBreak: 'break-word' }}>
                      {result.search_query}
                    </Typography>
                  </Box>

                  <Divider sx={{ my: 2 }} />

                  <Box>
                    <Typography variant="subtitle2" gutterBottom>
                      Classification Outputs
                    </Typography>
                    {renderResponses()}
                  </Box>
                </>
              )}
            </CardContent>
          </Card>
        )}
      </Box>
    </Container>
  );
};

export default Home;
