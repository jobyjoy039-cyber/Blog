package com.example.moviestream.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import com.example.moviestream.data.Movie
import com.example.moviestream.ui.theme.Brand

private val artPalettes = listOf(
    listOf(Color(0xFF3A1C71), Color(0xFFD76D77)),
    listOf(Color(0xFF0F2027), Color(0xFF2C5364)),
    listOf(Color(0xFF42275A), Color(0xFF734B6D)),
    listOf(Color(0xFF134E5E), Color(0xFF71B280)),
    listOf(Color(0xFF41295A), Color(0xFF2F0743)),
    listOf(Color(0xFF8E0E00), Color(0xFF1F1C18)),
)

/** Poster image, or generated title art when the movie has no image or it fails to load. */
@Composable
fun MovieArt(movie: Movie, modifier: Modifier = Modifier, showTitle: Boolean = true) {
    val fallback = @Composable {
        val palette = artPalettes[Math.floorMod(movie.id.hashCode(), artPalettes.size)]
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Brush.linearGradient(palette)),
            contentAlignment = Alignment.Center,
        ) {
            if (showTitle) {
                Text(
                    text = movie.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                    color = Color.White,
                    modifier = Modifier.padding(12.dp),
                )
            }
        }
    }
    Box(modifier) {
        if (movie.posterUrl == null) {
            fallback()
        } else {
            SubcomposeAsyncImage(
                model = movie.posterUrl,
                contentDescription = movie.title,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
                loading = { Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surfaceVariant)) },
                error = { fallback() },
            )
        }
    }
}

@Composable
fun PosterCard(
    movie: Movie,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    progress: Float? = null,
) {
    Column(modifier.width(120.dp)) {
        Box(
            Modifier
                .fillMaxWidth()
                .aspectRatio(2f / 3f)
                .clip(RoundedCornerShape(8.dp))
                .clickable(onClick = onClick),
        ) {
            MovieArt(movie, Modifier.fillMaxSize())
            if (progress != null) {
                LinearProgressIndicator(
                    progress = { progress },
                    color = Brand,
                    trackColor = Color.White.copy(alpha = 0.3f),
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .fillMaxWidth()
                        .height(4.dp),
                )
            }
        }
    }
}
