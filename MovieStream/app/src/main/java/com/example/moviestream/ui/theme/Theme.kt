package com.example.moviestream.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Brand = Color(0xFFE50914)
private val Background = Color(0xFF0E0E12)
private val Surface = Color(0xFF1A1A21)

private val colors = darkColorScheme(
    primary = Brand,
    onPrimary = Color.White,
    secondary = Color(0xFFB3B3C2),
    background = Background,
    onBackground = Color.White,
    surface = Background,
    onSurface = Color.White,
    surfaceVariant = Surface,
    onSurfaceVariant = Color(0xFFB3B3C2),
    surfaceContainer = Surface,
)

@Composable
fun MovieStreamTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = colors, content = content)
}
