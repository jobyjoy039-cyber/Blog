package com.example.moviestream.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Replay
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.moviestream.data.Movie
import com.example.moviestream.ui.MovieViewModel
import com.example.moviestream.ui.components.MovieArt
import com.example.moviestream.ui.theme.Brand

@Composable
fun DetailScreen(
    viewModel: MovieViewModel,
    movieId: String,
    onBack: () -> Unit,
    onPlay: (Movie, fromStart: Boolean) -> Unit,
) {
    val movie = viewModel.movie(movieId)
    val progressMap by viewModel.progress.collectAsStateWithLifecycle()
    val myList by viewModel.myListIds.collectAsStateWithLifecycle()

    if (movie == null) {
        Box(Modifier.fillMaxSize(), Alignment.Center) { Text("Movie not found") }
        return
    }
    val progress = progressMap[movie.id]?.takeIf { it.isResumable }
    val inMyList = movie.id in myList

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        Box(Modifier.fillMaxWidth().aspectRatio(16f / 9f)) {
            MovieArt(movie, Modifier.fillMaxSize())
            Box(
                Modifier.fillMaxSize().background(
                    Brush.verticalGradient(0.6f to Color.Transparent, 1f to MaterialTheme.colorScheme.background),
                ),
            )
            IconButton(onClick = onBack, modifier = Modifier.statusBarsPadding().padding(4.dp)) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
            }
        }
        Column(Modifier.padding(16.dp)) {
            Text(movie.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text(
                listOf(movie.year.toString(), movie.rating, "${movie.durationMinutes} min")
                    .filter { it.isNotBlank() && it != "0" }
                    .joinToString("  •  "),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = { onPlay(movie, false) },
                colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = Color.Black),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Filled.PlayArrow, contentDescription = null)
                Spacer(Modifier.width(4.dp))
                Text(if (progress != null) "Resume" else "Play")
            }
            if (progress != null) {
                LinearProgressIndicator(
                    progress = { progress.fraction },
                    color = Brand,
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                )
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { viewModel.toggleMyList(movie.id) }, modifier = Modifier.weight(1f)) {
                    Icon(if (inMyList) Icons.Filled.Check else Icons.Filled.Add, contentDescription = null)
                    Spacer(Modifier.width(4.dp))
                    Text("My List")
                }
                if (progress != null) {
                    OutlinedButton(onClick = { onPlay(movie, true) }, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Filled.Replay, contentDescription = null)
                        Spacer(Modifier.width(4.dp))
                        Text("Start over")
                    }
                }
            }
            Spacer(Modifier.height(16.dp))
            Text(movie.description, style = MaterialTheme.typography.bodyLarge)
            Spacer(Modifier.height(12.dp))
            Text(
                "Genres: ${movie.genres.joinToString(", ")}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (movie.credit.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    movie.credit,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
