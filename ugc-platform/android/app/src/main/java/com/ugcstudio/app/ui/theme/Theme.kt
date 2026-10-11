package com.ugcstudio.app.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

private val Coral = Color(0xFFE5484D)
private val CoralDark = Color(0xFFFF6369)

private val Light = lightColorScheme(
    primary = Coral, onPrimary = Color.White, primaryContainer = Color(0xFFFBEAEA),
    onPrimaryContainer = Color(0xFF5C1214), background = Color(0xFFF6F5F2), surface = Color.White,
)
private val Dark = darkColorScheme(
    primary = CoralDark, onPrimary = Color(0xFF1A0B0B), primaryContainer = Color(0xFF3A2223),
    onPrimaryContainer = Color(0xFFFFDADA), background = Color(0xFF151413), surface = Color(0xFF1E1D1B),
)

@Composable
fun UgcTheme(dynamic: Boolean = false, content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val scheme = when {
        dynamic && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (dark) dynamicDarkColorScheme(LocalContext.current) else dynamicLightColorScheme(LocalContext.current)
        dark -> Dark
        else -> Light
    }
    MaterialTheme(colorScheme = scheme, content = content)
}
