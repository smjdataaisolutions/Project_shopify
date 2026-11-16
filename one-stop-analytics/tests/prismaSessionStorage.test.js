import assert from "node:assert/strict";
import test from "node:test";

import { PrismaSessionStorage } from "@shopify/shopify-app-session-storage-prisma";

function createPrismaStub() {
  const rows = new Map();

  return {
    rows,
    prisma: {
      session: {
        async count() {
          return rows.size;
        },
        async upsert({ where, create, update }) {
          const row = rows.has(where.id) ? update : create;
          rows.set(where.id, { ...row });
          return row;
        },
        async findUnique({ where }) {
          return rows.get(where.id) ?? null;
        },
        async delete({ where }) {
          if (!rows.delete(where.id)) {
            throw new Error("Session not found");
          }
        },
        async deleteMany({ where }) {
          for (const id of where.id.in) rows.delete(id);
        },
        async findMany({ where }) {
          return [...rows.values()].filter((row) => row.shop === where.shop);
        },
      },
    },
  };
}

function createOnlineSession(id, shop) {
  const expires = new Date("2026-11-16T12:00:00.000Z");
  const refreshTokenExpires = new Date("2026-12-16T12:00:00.000Z");

  return {
    id,
    shop,
    state: "state-value",
    isOnline: true,
    scope: "read_orders,read_products",
    expires,
    accessToken: "test-access-token",
    refreshToken: "test-refresh-token",
    refreshTokenExpires,
    toObject() {
      return {
        refreshToken: this.refreshToken,
        refreshTokenExpires: this.refreshTokenExpires,
        onlineAccessInfo: {
          associated_user: {
            id: 12345,
            first_name: "Test",
            last_name: "Merchant",
            email: "merchant@example.test",
            account_owner: true,
            locale: "en",
            collaborator: false,
            email_verified: true,
          },
        },
      };
    },
  };
}

test("Prisma session storage preserves Shopify session CRUD behavior", async () => {
  const { prisma } = createPrismaStub();
  const storage = new PrismaSessionStorage(prisma, {
    connectionRetries: 1,
    connectionRetryIntervalMs: 0,
  });
  const shop = "security-test.myshopify.com";
  const first = createOnlineSession("online_security_test_1", shop);
  const second = createOnlineSession("online_security_test_2", shop);

  assert.equal(await storage.isReady(), true);
  assert.equal(await storage.storeSession(first), true);
  assert.equal(await storage.storeSession(second), true);

  const loaded = await storage.loadSession(first.id);
  assert.equal(loaded.id, first.id);
  assert.equal(loaded.shop, shop);
  assert.equal(loaded.accessToken, first.accessToken);
  assert.equal(loaded.refreshToken, first.refreshToken);
  assert.equal(loaded.refreshTokenExpires.getTime(), first.refreshTokenExpires.getTime());
  assert.equal(loaded.onlineAccessInfo.associated_user.id, 12345);

  const sessions = await storage.findSessionsByShop(shop);
  assert.deepEqual(
    sessions.map(({ id }) => id).sort(),
    [first.id, second.id],
  );

  assert.equal(await storage.deleteSession(first.id), true);
  assert.equal(await storage.loadSession(first.id), undefined);
  assert.equal(await storage.deleteSessions([second.id]), true);
  assert.deepEqual(await storage.findSessionsByShop(shop), []);
});
