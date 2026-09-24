package com.prooffoundry.cachevaultmobile.data.local

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/**
 * Phone-local vault storage, schema v1 (CV-MOBILE-1).
 *
 * Platform SQLiteOpenHelper is a deliberate scope choice for this tranche:
 * it supplies create/version hooks without a Kotlin/annotation-processor
 * upgrade. There is no destructive fallback — an unknown or newer schema is a
 * recoverable error that preserves the bytes on disk.
 *
 * Tables:
 *  - safes    — phone-local organizers (the default Safe is protected)
 *  - items    — text / link / image metadata + verbatim text bodies
 *  - assets   — phone-owned image files under app-private storage
 *  - activity — minimal truthful local event ledger (no payloads, no tokens)
 *  - meta     — schema/versioned preferences (install-local vault id)
 */
class LocalVaultDatabase(
    context: Context,
    private val dbName: String = DATABASE_NAME,
    private val dbVersion: Int = DATABASE_VERSION,
) : SQLiteOpenHelper(context, dbName, null, dbVersion) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """
            CREATE TABLE safes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """.trimIndent(),
        )
        db.execSQL(
            """
            CREATE TABLE items (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                preview TEXT NOT NULL,
                content TEXT,
                asset_id TEXT,
                content_hash TEXT,
                safe_id TEXT NOT NULL REFERENCES safes(id),
                is_favorite INTEGER NOT NULL DEFAULT 0,
                is_sensitive INTEGER NOT NULL DEFAULT 0,
                sensitive_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                removed_at TEXT
            )
            """.trimIndent(),
        )
        db.execSQL(
            """
            CREATE TABLE assets (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL REFERENCES items(id),
                file_name TEXT NOT NULL,
                mime TEXT NOT NULL,
                byte_count INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                width INTEGER,
                height INTEGER,
                state TEXT NOT NULL
            )
            """.trimIndent(),
        )
        db.execSQL(
            """
            CREATE TABLE activity (
                id TEXT PRIMARY KEY,
                item_id TEXT,
                at TEXT NOT NULL,
                action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                reason TEXT
            )
            """.trimIndent(),
        )
        db.execSQL(
            """
            CREATE TABLE meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """.trimIndent(),
        )
        db.execSQL("CREATE INDEX idx_items_safe ON items(safe_id)")
        db.execSQL("CREATE INDEX idx_items_removed ON items(removed_at)")
        db.execSQL("CREATE INDEX idx_items_created ON items(created_at)")
        db.execSQL("CREATE INDEX idx_assets_item ON assets(item_id)")
        db.execSQL("CREATE INDEX idx_activity_at ON activity(at)")

        db.insert(
            "safes",
            null,
            ContentValues().apply {
                put("id", DEFAULT_SAFE_ID)
                put("name", DEFAULT_SAFE_NAME)
                put("is_default", 1)
                put("created_at", java.time.Instant.now().toString())
            },
        )
    }

    /**
     * No migrations exist yet (schema v1). Opening a database with a newer
     * unknown version must fail loudly and leave the file intact — never
     * silently wipe the phone vault.
     */
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        throw android.database.sqlite.SQLiteException(
            "Unknown local vault schema upgrade $oldVersion → $newVersion; refusing to alter existing data.",
        )
    }

    override fun onDowngrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        throw android.database.sqlite.SQLiteException(
            "Local vault schema $oldVersion is newer than this app understands ($newVersion); data preserved.",
        )
    }

    companion object {
        const val DATABASE_NAME = "cache_vault_local.db"
        const val DATABASE_VERSION = 1
        const val DEFAULT_SAFE_ID = "default"
        const val DEFAULT_SAFE_NAME = "Default Safe"
    }
}
