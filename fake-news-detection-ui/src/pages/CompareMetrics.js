import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth } from '../firebase';
import { onAuthStateChanged } from 'firebase/auth';
import {
  Container, Box, Typography, Button, Select, MenuItem,
  FormControl, InputLabel, CircularProgress, Paper
} from '@mui/material';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend
} from 'recharts';

const API_BASE = process.env.REACT_APP_API_BASE_URL || '';
// Matplotlib default color cycle hexes
const COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c'];

export default function CompareMetrics() {
  const navigate = useNavigate();

  // auth & token
  const [token, setToken] = useState('');
  const [authChecked, setAuthChecked] = useState(false);

  // saved benchmarks for dropdowns
  const [savedRuns, setSavedRuns] = useState([]);

  // which IDs are selected
  const [ids, setIds] = useState(['', '', '']);

  // comparison fetch state
  const [loading, setLoading] = useState(false);
  const [imgs, setImgs]         = useState({ roc_comparison: '', pr_comparison: '' });
  const [prfData, setPrfData]   = useState([]);
  const [error, setError]       = useState("");

  // listen for auth
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async user => {
      if (user) {
        setToken(await user.getIdToken(true));
      } else {
        setToken('');
      }
      setAuthChecked(true);
    });
    return () => unsub();
  }, []);

  // load saved runs for dropdown
  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/benchmarks`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (!res.ok) throw new Error(res.statusText);
        setSavedRuns(await res.json());
      } catch (e) {
        console.error(e);
      }
    })();
  }, [token]);

  const handleChange = (idx, val) => {
    const next = [...ids]; next[idx] = val; setIds(next);
  };

  const fetchComparison = async () => {
    setLoading(true);
    setError("");
    try {
      const token = await auth.currentUser.getIdToken(true);
      const selected = ids.filter(i => i);
      const q = selected.join(",");

      // 1) fetch images
      const cmpRes = await fetch(
        `${API_BASE}/benchmarks/compare?ids=${encodeURIComponent(q)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!cmpRes.ok) throw new Error("Failed to load comparison plots");
      setImgs(await cmpRes.json());

      // 2) fetch metrics JSON
      const metricsList = await Promise.all(
        selected.map(async id => {
          const res = await fetch(
            `${API_BASE}/benchmark/${id}`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (!res.ok) throw new Error(`Failed to load metrics for ${id}`);
          const data = await res.json();
          return {
            id,
            precision: data.precision,
            recall:    data.recall,
            f1:        data.f1_score
          };
        })
      );

      // 3) build prfData
      const prfArray = ["precision","recall","f1"].map(metric => {
        const entry = {
          name: metric === "f1" ? "F1-score" : metric.charAt(0).toUpperCase() + metric.slice(1)
        };
        metricsList.forEach(m => {
          entry[m.id] = m[metric];
        });
        return entry;
      });
      setPrfData(prfArray);

    } catch (e) {
      console.error(e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (!authChecked) {
    return (
      <Container><Box textAlign="center" mt={10}><CircularProgress /><Typography>Checking authentication…</Typography></Box></Container>
    );
  }
  if (!token) {
    return (
      <Container><Box textAlign="center" mt={10}><Typography color="error">You must be signed in.</Typography></Box></Container>
    );
  }

  const selectedIds = ids.filter(i => i);

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Box mb={3} display="flex" alignItems="center" gap={2}>
        <Typography variant="h4">Compare Benchmarks</Typography>
        <Button variant="outlined" onClick={()=>navigate(-1)}>Back</Button>
      </Box>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle1">Select 2–3 runs to compare</Typography>
        <Box mt={1} display="flex" gap={2}>
          {[0,1,2].map(i => (
            <FormControl fullWidth size="small" key={i}>
              <InputLabel id={`cmp-${i}-label`}>Run {i+1}</InputLabel>
              <Select
                labelId={`cmp-${i}-label`}
                label={`Run ${i+1}`}
                value={ids[i]}
                onChange={e=>handleChange(i, e.target.value)}
              >
                <MenuItem value=""><em>None</em></MenuItem>
                {savedRuns.map(run => (
                  <MenuItem key={run.id} value={run.id}>
                    {run.timestamp
                      ? new Date(run.timestamp).toLocaleString()
                      : run.id
                    } (ID: {run.id})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          ))}
          <Button
            variant="contained"
            onClick={fetchComparison}
            disabled={loading || selectedIds.length < 2}
          >
            Compare
          </Button>
        </Box>
      </Paper>

      {loading && <CircularProgress />}
      {error   && <Typography color="error">{error}</Typography>}

      {/* 1) Bar chart up top, with matching colors */}
      {!loading && prfData.length > 0 && (
        <>
          <Typography variant="h6" gutterBottom>Precision / Recall / F1 Comparison</Typography>
          <BarChart
            width={600}
            height={300}
            data={prfData}
            margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
          >
            <XAxis dataKey="name" />
            <YAxis domain={[0,1]} tickFormatter={t=>`${(t*100).toFixed(0)}%`} />
            <Tooltip formatter={v=>`${(v*100).toFixed(1)}%`} />
            <Legend />
            {selectedIds.map((id, idx) => (
              <Bar
                key={id}
                dataKey={id}
                name={id}
                fill={COLORS[idx]}
              />
            ))}
          </BarChart>
        </>
      )}

      {/* 2) Matplotlib overlay images */}
      {!loading && imgs.roc_comparison && (
        <>
          <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>ROC Curve Comparison</Typography>
          <img
            src={`data:image/png;base64,${imgs.roc_comparison}`}
            alt="ROC Comparison"
            style={{ width: '100%', maxHeight: 400, objectFit: 'contain' }}
          />

          <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>Precision–Recall Comparison</Typography>
          <img
            src={`data:image/png;base64,${imgs.pr_comparison}`}
            alt="PR Comparison"
            style={{ width: '100%', maxHeight: 400, objectFit: 'contain' }}
          />
        </>
      )}
    </Container>
  );
}
