package com.prooffoundry.cachevaultmobile.data

import kotlin.math.ln

/**
 * Conservative-but-eager sensitive-content detector for warn-before-send.
 *
 * Mirrors the desktop `cache_vault.core.sensitive` shapes so the phone can warn
 * before sending a likely secret to the PC. It never logs content; callers pass
 * the shared text in and get back a short human reason (or null).
 */
object SensitiveText {

    private val PRIVATE_KEY = Regex("-----BEGIN [A-Z ]*PRIVATE KEY-----")
    private val JWT = Regex("""\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b""")
    private val KNOWN_PREFIX = Regex(
        "\\b(" +
            "sk-[A-Za-z0-9]{16,}" +
            "|AKIA[0-9A-Z]{16}" +
            "|ghp_[A-Za-z0-9]{20,}" +
            "|github_pat_[A-Za-z0-9_]{20,}" +
            "|gho_[A-Za-z0-9]{20,}" +
            "|xox[baprs]-[A-Za-z0-9-]{10,}" +
            "|AIza[0-9A-Za-z_-]{30,}" +
            "|glpat-[A-Za-z0-9_-]{16,}" +
            ")\\b",
    )
    private val ASSIGNMENT = Regex(
        "(?i)\\b(pass(?:word|wd)?|secret|token|api[_-]?key|access[_-]?key|" +
            "client[_-]?secret|auth)\\b\\s*[:=]\\s*\\S{4,}",
    )
    private val RECOVERY = Regex("(?i)\\b(recovery|backup|one[- ]?time)\\b.*\\bcode\\b")
    private val OTP = Regex("^\\d{6,8}$")
    private val CARD_CANDIDATE = Regex("\\b(?:\\d[ -]?){13,19}\\b")

    /** Short reason if [content] looks sensitive, else null. */
    fun reason(content: String?): String? {
        if (content.isNullOrBlank()) return null
        val text = content.trim()
        if (PRIVATE_KEY.containsMatchIn(text)) return "private key"
        if (JWT.containsMatchIn(text)) return "JWT token"
        if (KNOWN_PREFIX.containsMatchIn(text)) return "API key/token"
        if (ASSIGNMENT.containsMatchIn(text)) return "a password or token"
        if (RECOVERY.containsMatchIn(text)) return "a recovery code"
        if (OTP.matches(text)) return "a one-time code"
        for (m in CARD_CANDIDATE.findAll(text)) {
            if (luhnOk(m.value)) return "a card number"
        }
        if (highEntropySecret(text)) return "a high-entropy secret"
        return null
    }

    fun isSensitive(content: String?): Boolean = reason(content) != null

    private fun luhnOk(candidate: String): Boolean {
        val digits = candidate.filter { it.isDigit() }.map { it - '0' }
        if (digits.size !in 13..19) return false
        var checksum = 0
        val parity = digits.size % 2
        digits.forEachIndexed { i, d0 ->
            var d = d0
            if (i % 2 == parity) {
                d *= 2
                if (d > 9) d -= 9
            }
            checksum += d
        }
        return checksum % 10 == 0
    }

    private fun highEntropySecret(text: String): Boolean {
        val token = text.trim()
        if (token.length < 20) return false
        if (token.any { it == ' ' || it == '\n' || it == '\t' || it == '\r' || it == '\\' || it == '/' || it == ':' }) {
            return false
        }
        val parts = token.split(Regex("[._-]+")).filter { it.isNotEmpty() }
        val wordish = parts.filter { it.all(Char::isLetter) && it.length >= 3 }
        if (wordish.size >= 2) return false
        val hasUpper = token.any(Char::isUpperCase)
        val hasLower = token.any(Char::isLowerCase)
        val hasDigit = token.any(Char::isDigit)
        val classes = listOf(hasUpper, hasLower, hasDigit).count { it }
        return classes >= 2 && shannonEntropy(token) >= 3.5
    }

    private fun shannonEntropy(s: String): Double {
        if (s.isEmpty()) return 0.0
        val length = s.length.toDouble()
        return s.groupingBy { it }.eachCount().values.sumOf { c ->
            val p = c / length
            -p * (ln(p) / ln(2.0))
        }
    }
}
