import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { auth } from '../firebase';
import { onAuthStateChanged } from 'firebase/auth';
import {
  Container, Box, Typography, Button, Select, MenuItem,
  FormControl, InputLabel, CircularProgress, Paper
} from '@mui/material';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, LabelList
} from 'recharts';

const API_BASE = process.env.REACT_APP_API_BASE_URL || '';
const COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'];

export default function CompareMetrics() {
  const navigate = useNavigate();
  const [token, setToken] = useState('');
  const [authChecked, setAuthChecked] = useState(false);
  const [savedRuns, setSavedRuns] = useState([]);
  const [ids, setIds] = useState(['', '', '', '']);
  const [loading, setLoading] = useState(false);
  const [imgs, setImgs] = useState({ roc_comparison: '', pr_comparison: '' });
  const [prfData, setPrfData] = useState([]);
  const [runInfos, setRunInfos] = useState({});
  const [error, setError] = useState("");

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async user => {
      if (user) setToken(await user.getIdToken(true));
      else setToken('');
      setAuthChecked(true);
    });
    return () => unsub();
  }, []);

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/benchmarks`, { headers: { Authorization: `Bearer ${token}` } });
        if (!res.ok) throw new Error(res.statusText);
        setSavedRuns(await res.json());
      } catch (e) {
        console.error(e);
      }
    })();
  }, [token]);

  const handleChange = (idx, val) => {
    const next = [...ids];
    next[idx] = val;
    setIds(next);
  };

  const fetchComparison = async () => {
    setLoading(true);
    setError("");
    try {
      const token = await auth.currentUser.getIdToken(true);
      const selected = ids.filter(i => i);
      const q = selected.join(',');

      // fetch comparison images
      const cmpRes = await fetch(
        `${API_BASE}/benchmarks/compare?ids=${encodeURIComponent(q)}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!cmpRes.ok) throw new Error('Failed to load comparison plots');
      setImgs(await cmpRes.json());

      // fetch detailed metrics, including model, output_type, prompt_variant, use_external_info
      const metricsList = await Promise.all(
        selected.map(async id => {
          const res = await fetch(
            `${API_BASE}/benchmark/${id}`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (!res.ok) throw new Error(`Failed to load metrics for ${id}`);
          const data = await res.json();
          const params = data.parameters || {};
          const model = data.classify_model || params.classify_model || 'unknown';
          const outputType = data.output_type || params.output_type || 'unknown';
          const promptVar = data.prompt_variant || params.prompt_variant || 'unknown';
          const useExt = data.use_external_info ?? params.use_external_info ?? false;

          return {
            id,
            precision: data.precision,
            recall: data.recall,
            f1: data.f1_score,
            balanced_accuracy: data.balanced_accuracy,
            model,
            output_type: outputType,
            prompt_variant: promptVar,
            use_external_info: useExt
          };
        })
      );

      // store run info for legend labels
      const infoMap = {};
      metricsList.forEach(m => { infoMap[m.id] = m; });
      setRunInfos(infoMap);

      // prepare PRF data for chart
      const metrics = [
        { key: 'precision', name: 'Precision' },
        { key: 'recall', name: 'Recall' },
        { key: 'f1', name: 'F1-score' },
        { key: 'balanced_accuracy', name: 'BACC' }
      ];

      const prfArray = metrics.map(({ key, name }) => {
        const entry = { name };
        metricsList.forEach(m => { entry[m.id] = m[key]; });
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
      <Container>
        <Box textAlign="center" mt={10}>
          <CircularProgress />
          <Typography>Checking authentication…</Typography>
        </Box>
      </Container>
    );
  }

  if (!token) {
    return (
      <Container>
        <Box textAlign="center" mt={10}>
          <Typography color="error">You must be signed in.</Typography>
        </Box>
      </Container>
    );
  }

  const selectedIds = ids.filter(i => i);

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box mb={3} display="flex" alignItems="center" gap={2}>
        <Typography variant="h3">Compare Benchmarks</Typography>
        <Button variant="outlined" onClick={() => navigate(-1)}>Back</Button>
      </Box>

      <Paper sx={{ p: 3, mb: 4 }}>
        <Typography variant="h6">Select 2–4 runs to compare</Typography>
        <Box mt={2} display="flex" gap={2} flexWrap="wrap">
          {ids.map((_, i) => (
            <FormControl fullWidth size="medium" key={i} sx={{ minWidth: 160 }}>
              <InputLabel id={`cmp-${i}-label`}>Run {i + 1}</InputLabel>
              <Select
                labelId={`cmp-${i}-label`}
                label={`Run ${i + 1}`}
                value={ids[i]}
                onChange={e => handleChange(i, e.target.value)}
              >
                <MenuItem value=""><em>None</em></MenuItem>
                {savedRuns.map(run => (
                  <MenuItem key={run.id} value={run.id}>
                    {run.timestamp ? new Date(run.timestamp).toLocaleString() : run.id} (ID: {run.id})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          ))}
          <Button
            variant="contained"
            size="large"
            onClick={fetchComparison}
            disabled={loading || selectedIds.length < 2}
            sx={{ minHeight: 56 }}
          >Compare</Button>
        </Box>
      </Paper>

      {loading && <CircularProgress size={80} />}
      {error && <Typography color="error" variant="h6">{error}</Typography>}

      {!loading && prfData.length > 0 && (
        <>
          <Typography variant="h4" gutterBottom>
            Precision / Recall / F1 / BACC Comparison
          </Typography>
          <BarChart
            width={1000}
            height={500}
            data={prfData}
            margin={{ top: 40, right: 40, left: 40, bottom: 20 }}
            barCategoryGap="100%"
            barGap={40}
          >
            <XAxis dataKey="name" interval={0} tick={{ fontSize: 16 }} />
            <YAxis domain={[0, 1]} tickFormatter={t => `${(t * 100).toFixed(0)}%`} tick={{ fontSize: 16 }} />
            <Tooltip formatter={v => `${(v * 100).toFixed(1)}%`} contentStyle={{ fontSize: 14 }} />
            <Legend />
            {selectedIds.map((id, idx) => {
              const info = runInfos[id] || {};
              const { model, output_type, prompt_variant, use_external_info } = info;
              const extStr = use_external_info ? 'external info' : 'no external info';
              const legendLabel = `${id} (${model}, ${output_type}, ${prompt_variant}, ${extStr})`;

              return (
                <Bar key={id} dataKey={id} name={legendLabel} fill={COLORS[idx]} barSize={60}>
                  <LabelList
                    dataKey={id}
                    position="inside"
                    fill="#ffffff"
                    formatter={v => `${(v * 100).toFixed(1)}%`}
                    style={{ fontSize: 14 }}
                  />
                </Bar>
              );
            })}
          </BarChart>
        </>
      )}

      {!loading && imgs.roc_comparison && (
        <>
          <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>
            ROC Curve Comparison
          </Typography>
          <img src={`data:image/png;base64,${imgs.roc_comparison}`} alt="ROC Comparison" style={{ width: '100%', maxHeight: 400, objectFit: 'contain' }} />

          <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>
            Precision–Recall Comparison
          </Typography>
          <img src={`data:image/png;base64,${imgs.pr_comparison}`} alt="PR Comparison" style={{ width: '100%', maxHeight: 400, objectFit: 'contain' }} />
        </>
      )}
    </Container>
  );
}