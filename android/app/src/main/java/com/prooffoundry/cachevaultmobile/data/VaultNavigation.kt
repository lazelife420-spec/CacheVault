package com.prooffoundry.cachevaultmobile.data

enum class BrowseFilter(val label: String) {
    ALL("All"),
    FAVORITES("Favorites"),
    TEXT("Text"),
    LINKS("Links"),
    CODE("Code"),
    COMMANDS("Commands"),
    FILES("Files"),
    SENSITIVE("Sensitive"),
    REMOVED("Removed"),
}

enum class VaultSectionKind(
    val label: String,
    val helper: String,
) {
    TEXT("Text Clips", "Plain text saved on your PC"),
    LINKS("Links", "URLs and web references"),
    CODE("Code", "Saved snippets and code"),
    COMMANDS("Commands", "Shell and command lines"),
    SCREENSHOTS("Screenshots", "Images saved from your PC"),
    FAVORITES("Favorites", "Starred on your PC"),
    PROOF("Proof Receipts", "Local proof history"),
    RECENT("Recently Saved", "Newest clips first"),
    SENSITIVE("Sensitive", "Handle with care"),
    REMOVED("Recently Removed", "Restorable removed clips"),
}

data class VaultSectionCounts(
    val text: Int = 0,
    val links: Int = 0,
    val code: Int = 0,
    val commands: Int = 0,
    val screenshots: Int = 0,
    val favorites: Int = 0,
    val recentlySaved: Int = 0,
    val sensitive: Int = 0,
    val recentlyRemoved: Int = 0,
) {
    fun countFor(kind: VaultSectionKind): Int = when (kind) {
        VaultSectionKind.TEXT -> text
        VaultSectionKind.LINKS -> links
        VaultSectionKind.CODE -> code
        VaultSectionKind.COMMANDS -> commands
        VaultSectionKind.SCREENSHOTS -> screenshots
        VaultSectionKind.FAVORITES -> favorites
        VaultSectionKind.PROOF -> 0
        VaultSectionKind.RECENT -> recentlySaved
        VaultSectionKind.SENSITIVE -> sensitive
        VaultSectionKind.REMOVED -> recentlyRemoved
    }
}
