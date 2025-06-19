import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Container, Box, Typography, Button, Divider
} from '@mui/material';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  LineChart, Line, CartesianGrid
} from 'recharts';
import { Table, TableBody, TableCell, TableHead, TableRow, Paper } from '@mui/material';


const Metrics = () => {
  const { state } = useLocation();
  const navigate = useNavigate();

  const raw = state?.metrics || {};
  // merge summary metrics and params so output_type is on data
  const data = { ...(raw.metrics ? raw.metrics : raw), ...(raw.params || {}) };
  console.log(data.output_type)

  if (!data) {
    return (
      <Container>
        <Typography color="error">No metrics data available.</Typography>
        <Button onClick={() => navigate(-1)}>Back</Button>
      </Container>
    );
  }

  // 1) PRF bar data
  const prfData = [
    { name: 'Precision', value: data.precision },
    { name: 'Recall',    value: data.recall    },
    { name: 'F1-score',  value: data.f1_score  },
  ];

  // 2) ROC curve: one point per individual score
const hasResults = Array.isArray(data.results) && data.results.length > 0;
let rocData = [];
if (hasResults) {
    const flatScores = data.results.flatMap(r => r.scores);
    const flatTrue   = data.results.flatMap(r => r.scores.map(() => r.gold_binary ? 1 : 0));
  
    // unique sorted thresholds (desc)
    let thresholds = Array.from(new Set(flatScores)).sort((a,b) => b - a);
  
    // prepend a value above the max so you get the (0,0) point
    const maxScore = thresholds[0];
    thresholds = [maxScore + Number.EPSILON, ...thresholds];
  
    // append a value below the min so you get the (1,1) point (optional)
    const minScore = thresholds[thresholds.length-1];
    thresholds.push(minScore - Number.EPSILON);
  
    // build your ROC points
    rocData = thresholds.map(thr => {
      let tp=0, fp=0, tn=0, fn=0;
      flatScores.forEach((sc,i) => {
        const pred = sc >= thr ? 1 : 0;
        const gt   = flatTrue[i];
        if (pred===1 && gt===1) tp++;
        if (pred===1 && gt===0) fp++;
        if (pred===0 && gt===0) tn++;
        if (pred===0 && gt===1) fn++;
      });
      return {
        threshold: thr,
        fpr: fp + tn > 0 ? fp/(fp+tn) : 0,
        tpr: tp + fn > 0 ? tp/(tp+fn) : 0
      };
    });
  
    // finally, sort by fpr so the line actually draws left→right
    rocData.sort((a,b) => a.fpr - b.fpr);
  }
  // 3) Score histogram
  const { bin_edges, counts } = data.score_histogram;
  const histData = counts.map((cnt,i) => ({
    bin:   `${bin_edges[i].toFixed(1)}–${bin_edges[i+1].toFixed(1)}`,
    count: cnt
  }));

  // 4) Iteration accuracy
  const iterData = data.iteration_accuracy.map((acc,i) => ({
    iteration: i+1,
    accuracy:  acc
  }));

  return (
    <Container maxWidth="md">
      <Box my={4}>
        <Typography variant="h4" align="center" gutterBottom>
          Benchmark Detailed Metrics
        </Typography>
        <Box textAlign="right" mb={2}>
          <Button variant="outlined" onClick={() => navigate(-1)}>
            Back to Benchmark
          </Button>
        </Box>

        <Typography variant="h6" gutterBottom>
          Precision / Recall / F1
        </Typography>
        <BarChart width={500} height={250} data={prfData}>
          <XAxis dataKey="name" />
          <YAxis domain={[0,1]} tickFormatter={t => `${(t*100).toFixed(0)}%`} />
          <Tooltip formatter={v => `${(v*100).toFixed(1)}%`} />
          <Bar dataKey="value" fill="#8884d8" />
        </BarChart>

        <Divider sx={{ my: 4 }} />

       {/* ROC + Confusion Matrix */}
<Box display="flex" gap={4} flexWrap="wrap" justifyContent="space-between">
  {/* Only show ROC when we have continuous scores */}
  {data.output_type === 'score' ? (
    <Box flex="1 1 48%">
      <Typography variant="h6" gutterBottom>
        ROC Curve
      </Typography>
      <LineChart
        width={400}
        height={250}
        data={rocData}
        margin={{ top: 10, right: 20, left: 0, bottom: 10 }}
      >
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="fpr"
          domain={[0,1]}
          tickFormatter={t => `${(t*100).toFixed(0)}%`}
        />
        <YAxis
          type="number"
          dataKey="tpr"
          domain={[0,1]}
          tickFormatter={t => `${(t*100).toFixed(0)}%`}
        />
        <Tooltip
          formatter={v => `${(v*100).toFixed(1)}%`}
          labelFormatter={l => `Threshold: ${l.toFixed(2)}`}
        />
        <Line type="monotone" dataKey="tpr" stroke="#ff7300" dot={false} />
        <Line
          type="linear"
          data={[{ fpr:0, tpr:0 }, { fpr:1, tpr:1 }]}
          stroke="#ccc"
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </Box>
  ) : (
    <Box flex="1 1 48%">
      <Typography variant="h6" gutterBottom>
        ROC Curve (only available in Score mode)
      </Typography>
      <Typography color="textSecondary">
        Switch Output Type to “Score” to view.
      </Typography>
    </Box>
  )}

  {/* Confusion Matrix always shows */}
  <Box flex="1 1 48%">
    <Typography variant="h6" gutterBottom>
      Confusion Matrix
    </Typography>
    <Paper variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell />
            <TableCell align="center"><strong>Pred False</strong></TableCell>
            <TableCell align="center"><strong>Pred True</strong></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          <TableRow>
            <TableCell><strong>Actual False</strong></TableCell>
            <TableCell align="center">{data.confusion_matrix.TN}</TableCell>
            <TableCell align="center">{data.confusion_matrix.FP}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell><strong>Actual True</strong></TableCell>
            <TableCell align="center">{data.confusion_matrix.FN}</TableCell>
            <TableCell align="center">{data.confusion_matrix.TP}</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </Paper>
  </Box>
</Box>
        <Divider sx={{ my: 4 }} />

        <Typography variant="h6" gutterBottom>
          Score Distribution
        </Typography>
        <BarChart width={500} height={250} data={histData}>
          <XAxis dataKey="bin" angle={-45} textAnchor="end" interval={0} />
          <YAxis />
          <Tooltip />
          <Bar dataKey="count" fill="#ffc658" />
        </BarChart>

        <Divider sx={{ my: 4 }} />

        <Typography variant="h6" gutterBottom>
          Accuracy by Iteration
        </Typography>
        <LineChart width={500} height={250} data={iterData}>
          <XAxis dataKey="iteration" />
          <YAxis domain={[0,1]} tickFormatter={t => `${(t*100).toFixed(0)}%`} />
          <Tooltip formatter={v => `${(v*100).toFixed(1)}%`} />
          <Line type="monotone" dataKey="accuracy" stroke="#82ca9d" />
        </LineChart>
      </Box>
    </Container>
  );
};

export default Metrics;
