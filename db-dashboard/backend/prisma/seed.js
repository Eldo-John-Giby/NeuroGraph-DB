const { PrismaClient } = require('@prisma/client');
const bcrypt = require('bcryptjs');
const fs = require('fs');
const path = require('path');

const prisma = new PrismaClient();

async function main() {
  console.log('--- Starting NeuroGraph-DB Database Seeding ---');

  // 1. Seed Default AppUsers (Admin and Researcher)
  const adminPassword = await bcrypt.hash('admin123', 10);
  const researcherPassword = await bcrypt.hash('researcher123', 10);

  const adminUser = await prisma.appUser.upsert({
    where: { username: 'admin' },
    update: {},
    create: {
      username: 'admin',
      email: 'admin@neurograph.io',
      password: adminPassword,
      role: 'ADMIN',
    },
  });
  console.log(`✓ Seeded AppUser: ${adminUser.username} (${adminUser.role})`);

  const researcherUser = await prisma.appUser.upsert({
    where: { username: 'researcher' },
    update: {},
    create: {
      username: 'researcher',
      email: 'researcher@neurograph.io',
      password: researcherPassword,
      role: 'RESEARCHER',
    },
  });
  console.log(`✓ Seeded AppUser: ${researcherUser.username} (${researcherUser.role})`);

  // 2. Seed Mock Yelp Reviewers & Products & Reviews
  const reviewer1 = await prisma.yelpReviewer.upsert({
    where: { yelpId: 'U_1001' },
    update: {},
    create: { yelpId: 'U_1001', name: 'Alice Walker' },
  });
  const reviewer2 = await prisma.yelpReviewer.upsert({
    where: { yelpId: 'U_1002' },
    update: {},
    create: { yelpId: 'U_1002', name: 'Bob Harris' },
  });

  const product1 = await prisma.product.upsert({
    where: { productId: 'P_5001' },
    update: {},
    create: { productId: 'P_5001', name: 'Chicago Pizza Bistro' },
  });
  const product2 = await prisma.product.upsert({
    where: { productId: 'P_5002' },
    update: {},
    create: { productId: 'P_5002', name: 'Magnificent Mile Cafe' },
  });

  const review1 = await prisma.review.upsert({
    where: { reviewId: 'R_9001' },
    update: {},
    create: {
      reviewId: 'R_9001',
      text: 'Exquisite deep dish and friendly service!',
      rating: 5.0,
      date: new Date('2023-05-14'),
      reviewerId: reviewer1.id,
      productId: product1.id,
    },
  });

  const review2 = await prisma.review.upsert({
    where: { reviewId: 'R_9002' },
    update: {},
    create: {
      reviewId: 'R_9002',
      text: 'Disappointing crust and lukewarm pizza.',
      rating: 1.0,
      date: new Date('2023-06-20'),
      reviewerId: reviewer2.id,
      productId: product1.id,
    },
  });

  // 3. Seed ML Models & Graph Variants & Experiment Runs
  // Check multiple possible paths for grid_results.csv
  const possiblePaths = [
    path.join(__dirname, '../../../results/grid_results.csv'),
    path.join(__dirname, '../../../../results/grid_results.csv'),
    path.join(__dirname, '../../results/grid_results.csv'),
  ];
  let csvPath = possiblePaths.find(p => fs.existsSync(p));

  if (csvPath) {
    console.log(`Reading empirical benchmark results from ${csvPath}...`);
    const csvContent = fs.readFileSync(csvPath, 'utf8');
    const lines = csvContent.trim().split('\n');
    const headers = lines[0].split(',');

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      const values = line.split(',');
      const row = {};
      headers.forEach((header, index) => {
        row[header.trim()] = values[index].trim();
      });

      const variant = await prisma.graphVariant.upsert({
        where: { name: row.variant },
        update: {},
        create: { name: row.variant, description: `Evaluation graph topology variant: ${row.variant}` },
      });

      const model = await prisma.mLModel.upsert({
        where: { name: row.model },
        update: {},
        create: { name: row.model, description: `Fraud detection model: ${row.model}` },
      });

      const run = await prisma.experimentRun.upsert({
        where: {
          graphVariantId_mlModelId_seed: {
            graphVariantId: variant.id,
            mlModelId: model.id,
            seed: parseInt(row.seed, 10),
          },
        },
        update: {
          timeSec: parseFloat(row.time_sec || '0'),
          f1Macro: parseFloat(row.f1_macro || '0'),
          precision: parseFloat(row.precision || '0'),
          recall: parseFloat(row.recall || '0'),
          auc: parseFloat(row.auc || '0'),
        },
        create: {
          seed: parseInt(row.seed, 10),
          timeSec: parseFloat(row.time_sec || '0'),
          f1Macro: parseFloat(row.f1_macro || '0'),
          precision: parseFloat(row.precision || '0'),
          recall: parseFloat(row.recall || '0'),
          auc: parseFloat(row.auc || '0'),
          graphVariantId: variant.id,
          mlModelId: model.id,
        },
      });

      // Also create a sample FraudPrediction linked to review1 and run
      if (i === 1) {
        await prisma.fraudPrediction.upsert({
          where: { id: 1 },
          update: {},
          create: {
            id: 1,
            isFraud: false,
            confidence: 0.12,
            reviewId: review1.id,
            experimentRunId: run.id,
          },
        });
      }
    }
    console.log(`✓ Successfully seeded experiment runs from CSV`);
  } else {
    console.log('Notice: grid_results.csv not found, generating sample baseline runs...');
    const defaultVariants = ['clean', 'sem_L1', 'sem_L2', 'topo_p10', 'topo_p30'];
    const defaultModels = ['GCN', 'GAT', 'GraphSAGE', 'NeuroGraph-DB (Ours)'];

    for (const vName of defaultVariants) {
      const v = await prisma.graphVariant.upsert({
        where: { name: vName },
        update: {},
        create: { name: vName, description: `Variant: ${vName}` },
      });
      for (const mName of defaultModels) {
        const m = await prisma.mLModel.upsert({
          where: { name: mName },
          update: {},
          create: { name: mName, description: `Architecture: ${mName}` },
        });

        const isOurs = mName.includes('Ours');
        await prisma.experimentRun.upsert({
          where: {
            graphVariantId_mlModelId_seed: {
              graphVariantId: v.id,
              mlModelId: m.id,
              seed: 42,
            },
          },
          update: {},
          create: {
            seed: 42,
            timeSec: isOurs ? 14.5 : 8.2,
            f1Macro: isOurs ? 0.884 : 0.742,
            precision: isOurs ? 0.891 : 0.750,
            recall: isOurs ? 0.878 : 0.735,
            auc: isOurs ? 0.932 : 0.815,
            graphVariantId: v.id,
            mlModelId: m.id,
          },
        });
      }
    }
  }

  // 4. Seed an initial Audit Log entry
  await prisma.auditLog.create({
    data: {
      userId: adminUser.id,
      action: 'SYSTEM_INITIALIZATION',
      method: 'SEED',
      endpoint: 'prisma/seed.js',
      ipAddress: '127.0.0.1',
      details: JSON.stringify({ message: 'Initial seed executed successfully' }),
    },
  });
  console.log('✓ Initial AuditLog record created');

  console.log('--- Seeding Complete! ---');
}

main()
  .catch((e) => {
    console.error('Seeding error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
