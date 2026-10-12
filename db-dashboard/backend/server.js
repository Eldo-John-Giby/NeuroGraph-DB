const express = require('express');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { PrismaClient } = require('@prisma/client');
const { JWT_SECRET, authenticateToken, requireRole } = require('./middleware/auth');
const { createAuditLogger } = require('./middleware/audit');

const prisma = new PrismaClient();
const app = express();

app.use(cors());
app.use(express.json());

// Industry Best Practice: Audit logging middleware on all state-changing requests
app.use(createAuditLogger(prisma));

// -----------------------------------------------------------------------------
// Health Check
// -----------------------------------------------------------------------------
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'NeuroGraph-DB backend is running' });
});

// -----------------------------------------------------------------------------
// Authentication Endpoints (JWT & Role-Based Access Control)
// -----------------------------------------------------------------------------
// POST /api/auth/register (Create new user with default RESEARCHER role or specified)
app.post('/api/auth/register', async (req, res) => {
  try {
    const { username, email, password, role } = req.body;
    if (!username || !email || !password) {
      return res.status(400).json({ error: 'Username, email, and password are required' });
    }

    const existing = await prisma.appUser.findFirst({
      where: { OR: [{ username }, { email }] },
    });
    if (existing) {
      return res.status(400).json({ error: 'Username or email already exists' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);
    const userRole = role === 'ADMIN' ? 'ADMIN' : 'RESEARCHER';

    const user = await prisma.appUser.create({
      data: {
        username,
        email,
        password: hashedPassword,
        role: userRole,
      },
    });

    const token = jwt.sign(
      { id: user.id, username: user.username, email: user.email, role: user.role },
      JWT_SECRET,
      { expiresIn: '7d' }
    );

    res.status(201).json({
      message: 'User registered successfully',
      token,
      user: { id: user.id, username: user.username, email: user.email, role: user.role },
    });
  } catch (err) {
    console.error('Registration error:', err);
    res.status(500).json({ error: 'Registration failed' });
  }
});

// POST /api/auth/login
app.post('/api/auth/login', async (req, res) => {
  try {
    const { username, password } = req.body;
    if (!username || !password) {
      return res.status(400).json({ error: 'Username and password are required' });
    }

    const user = await prisma.appUser.findUnique({
      where: { username },
    });
    if (!user) {
      return res.status(401).json({ error: 'Invalid username or password' });
    }

    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) {
      return res.status(401).json({ error: 'Invalid username or password' });
    }

    const token = jwt.sign(
      { id: user.id, username: user.username, email: user.email, role: user.role },
      JWT_SECRET,
      { expiresIn: '7d' }
    );

    res.json({
      token,
      user: { id: user.id, username: user.username, email: user.email, role: user.role },
    });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ error: 'Login failed' });
  }
});

// GET /api/auth/me (Protected: Verify current session)
app.get('/api/auth/me', authenticateToken, async (req, res) => {
  try {
    const user = await prisma.appUser.findUnique({
      where: { id: req.user.id },
      select: { id: true, username: true, email: true, role: true, createdAt: true },
    });
    if (!user) return res.status(404).json({ error: 'User not found' });
    res.json({ user });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch user profile' });
  }
});

// -----------------------------------------------------------------------------
// Advanced SQL Endpoints (Raw SQL View, Stored Procedure, Trigger)
// -----------------------------------------------------------------------------
// GET /api/advanced/view (Raw SQL View: v_model_performance_summary)
app.get('/api/advanced/view', authenticateToken, async (req, res) => {
  try {
    const summary = await prisma.$queryRawUnsafe(`
      SELECT * FROM v_model_performance_summary;
    `);
    res.json(summary);
  } catch (err) {
    console.error('Error querying view:', err);
    res.status(500).json({ error: 'Failed to query SQL view: ' + err.message });
  }
});

// POST /api/advanced/procedure (Raw SQL Stored Procedure: sp_record_experiment_run)
// Requires ADMIN role
app.post('/api/advanced/procedure', authenticateToken, requireRole('ADMIN'), async (req, res) => {
  try {
    const { modelName, variantName, seed, timeSec, f1Macro, precision, recall, auc } = req.body;
    if (!modelName || !variantName || seed === undefined) {
      return res.status(400).json({ error: 'modelName, variantName, seed are required' });
    }

    await prisma.$executeRawUnsafe(`
      CALL sp_record_experiment_run(
        $1::text, $2::text, $3::int, $4::float8, $5::float8, $6::float8, $7::float8, $8::float8
      );
    `, modelName, variantName, Number(seed), Number(timeSec || 0), Number(f1Macro || 0), Number(precision || 0), Number(recall || 0), Number(auc || 0));

    res.json({ message: 'Stored procedure executed successfully' });
  } catch (err) {
    console.error('Error executing procedure:', err);
    res.status(500).json({ error: 'Failed to execute procedure: ' + err.message });
  }
});

// -----------------------------------------------------------------------------
// Experiment Runs CRUD with Search, Filtering, and Pagination
// -----------------------------------------------------------------------------
// GET /api/runs (Search, Filtering, Pagination)
app.get('/api/runs', authenticateToken, async (req, res) => {
  try {
    const page = Math.max(1, parseInt(req.query.page) || 1);
    const limit = Math.max(1, Math.min(100, parseInt(req.query.limit) || 10));
    const skip = (page - 1) * limit;

    const { modelId, variantId, search, minAuc } = req.query;

    const where = {};
    if (modelId) where.mlModelId = parseInt(modelId);
    if (variantId) where.graphVariantId = parseInt(variantId);
    if (minAuc) where.auc = { gte: parseFloat(minAuc) };

    if (search) {
      where.OR = [
        { mlModel: { name: { contains: search, mode: 'insensitive' } } },
        { graphVariant: { name: { contains: search, mode: 'insensitive' } } },
      ];
    }

    const [total, runs] = await Promise.all([
      prisma.experimentRun.count({ where }),
      prisma.experimentRun.findMany({
        where,
        skip,
        take: limit,
        orderBy: { id: 'desc' },
        include: {
          mlModel: true,
          graphVariant: true,
        },
      }),
    ]);

    res.json({
      data: runs,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    });
  } catch (err) {
    console.error('Error fetching runs:', err);
    res.status(500).json({ error: 'Failed to fetch runs' });
  }
});

// GET /api/runs/:id (Read Single)
app.get('/api/runs/:id', authenticateToken, async (req, res) => {
  try {
    const run = await prisma.experimentRun.findUnique({
      where: { id: parseInt(req.params.id) },
      include: {
        mlModel: true,
        graphVariant: true,
        predictions: { take: 50 },
      },
    });
    if (!run) return res.status(404).json({ error: 'Experiment run not found' });
    res.json(run);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch run details' });
  }
});

// POST /api/runs (Create - Admin or Researcher)
app.post('/api/runs', authenticateToken, async (req, res) => {
  try {
    const { seed, timeSec, f1Macro, precision, recall, auc, graphVariantId, mlModelId } = req.body;
    if (!graphVariantId || !mlModelId || seed === undefined) {
      return res.status(400).json({ error: 'graphVariantId, mlModelId, and seed are required' });
    }

    const newRun = await prisma.experimentRun.create({
      data: {
        seed: parseInt(seed),
        timeSec: parseFloat(timeSec || 0),
        f1Macro: parseFloat(f1Macro || 0),
        precision: parseFloat(precision || 0),
        recall: parseFloat(recall || 0),
        auc: parseFloat(auc || 0),
        graphVariantId: parseInt(graphVariantId),
        mlModelId: parseInt(mlModelId),
      },
      include: {
        mlModel: true,
        graphVariant: true,
      },
    });

    res.status(201).json(newRun);
  } catch (err) {
    console.error('Error creating run:', err);
    res.status(500).json({ error: 'Failed to create run: ' + err.message });
  }
});

// PUT /api/runs/:id (Update - Protected)
app.put('/api/runs/:id', authenticateToken, async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    const { timeSec, f1Macro, precision, recall, auc } = req.body;

    const updated = await prisma.experimentRun.update({
      where: { id },
      data: {
        ...(timeSec !== undefined && { timeSec: parseFloat(timeSec) }),
        ...(f1Macro !== undefined && { f1Macro: parseFloat(f1Macro) }),
        ...(precision !== undefined && { precision: parseFloat(precision) }),
        ...(recall !== undefined && { recall: parseFloat(recall) }),
        ...(auc !== undefined && { auc: parseFloat(auc) }),
      },
      include: {
        mlModel: true,
        graphVariant: true,
      },
    });

    res.json(updated);
  } catch (err) {
    console.error('Error updating run:', err);
    res.status(500).json({ error: 'Failed to update run: ' + err.message });
  }
});

// DELETE /api/runs/:id (Delete - Admin Only)
app.delete('/api/runs/:id', authenticateToken, requireRole('ADMIN'), async (req, res) => {
  try {
    const id = parseInt(req.params.id);
    // Delete predictions first if any
    await prisma.fraudPrediction.deleteMany({ where: { experimentRunId: id } });
    await prisma.experimentRun.delete({ where: { id } });
    res.json({ message: `Experiment run ${id} deleted successfully` });
  } catch (err) {
    console.error('Error deleting run:', err);
    res.status(500).json({ error: 'Failed to delete run: ' + err.message });
  }
});

// -----------------------------------------------------------------------------
// Graph Variants & ML Models Lookup Endpoints
// -----------------------------------------------------------------------------
app.get('/api/models', authenticateToken, async (req, res) => {
  try {
    const models = await prisma.mLModel.findMany({ orderBy: { name: 'asc' } });
    res.json(models);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch models' });
  }
});

app.get('/api/variants', authenticateToken, async (req, res) => {
  try {
    const variants = await prisma.graphVariant.findMany({ orderBy: { name: 'asc' } });
    res.json(variants);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch variants' });
  }
});

// -----------------------------------------------------------------------------
// Audit Logs (Admin Only)
// -----------------------------------------------------------------------------
app.get('/api/audit-logs', authenticateToken, requireRole('ADMIN'), async (req, res) => {
  try {
    const page = Math.max(1, parseInt(req.query.page) || 1);
    const limit = Math.max(1, Math.min(100, parseInt(req.query.limit) || 20));
    const skip = (page - 1) * limit;

    const [total, logs] = await Promise.all([
      prisma.auditLog.count(),
      prisma.auditLog.findMany({
        skip,
        take: limit,
        orderBy: { timestamp: 'desc' },
        include: {
          user: { select: { id: true, username: true, role: true } },
        },
      }),
    ]);

    res.json({
      data: logs,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    });
  } catch (err) {
    console.error('Error fetching audit logs:', err);
    res.status(500).json({ error: 'Failed to fetch audit logs' });
  }
});

// -----------------------------------------------------------------------------
// Server Initialization
// -----------------------------------------------------------------------------
const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});

module.exports = app;
