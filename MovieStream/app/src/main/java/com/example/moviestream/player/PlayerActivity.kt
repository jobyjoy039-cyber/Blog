package com.example.moviestream.player

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Pair
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.example.moviestream.data.Movie
import com.example.moviestream.data.UserLibrary

/**
 * Full-screen ExoPlayer. Handles progressive files (MP4/MKV/WebM/MOV) plus HLS and DASH adaptive
 * streams, and remembers where the viewer stopped so they can resume later.
 */
@UnstableApi
class PlayerActivity : ComponentActivity() {

    private lateinit var playerView: PlayerView
    private var player: ExoPlayer? = null
    private lateinit var library: UserLibrary

    private val url by lazy { intent.getStringExtra(EXTRA_URL).orEmpty() }
    private val movieId by lazy { intent.getStringExtra(EXTRA_MOVIE_ID) }
    private val title by lazy { intent.getStringExtra(EXTRA_TITLE) }

    /** Position to start from; updated when we tear the player down so it survives onStop/onStart. */
    private var startPositionMs = C.TIME_UNSET
    private var playWhenReady = true

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        library = UserLibrary.get(this)

        if (url.isBlank()) {
            finish()
            return
        }

        startPositionMs = when {
            savedInstanceState != null -> savedInstanceState.getLong(STATE_POSITION, C.TIME_UNSET)
            intent.getBooleanExtra(EXTRA_FROM_START, false) -> 0L
            else -> movieId?.let { library.progress.value[it] }?.takeIf { it.isResumable }?.positionMs ?: 0L
        }
        playWhenReady = savedInstanceState?.getBoolean(STATE_PLAY_WHEN_READY, true) ?: true

        playerView = PlayerView(this).apply {
            keepScreenOn = true
            setShowSubtitleButton(true)
            setFullscreenButtonClickListener { finish() }
            setErrorMessageProvider { error ->
                Pair.create(0, "Can't play this video (${error.errorCodeName}). Check the link and your connection.")
            }
        }
        setContentView(playerView)
        hideSystemBars()
    }

    override fun onStart() {
        super.onStart()
        initializePlayer()
    }

    override fun onResume() {
        super.onResume()
        hideSystemBars()
    }

    override fun onStop() {
        super.onStop()
        releasePlayer()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putLong(STATE_POSITION, player?.currentPosition ?: startPositionMs)
        outState.putBoolean(STATE_PLAY_WHEN_READY, player?.playWhenReady ?: playWhenReady)
    }

    private fun initializePlayer() {
        if (player != null) return
        val mediaItem = MediaItem.Builder()
            .setUri(url)
            .setMediaMetadata(MediaMetadata.Builder().setTitle(title).build())
            .build()

        player = ExoPlayer.Builder(this)
            .setSeekBackIncrementMs(10_000)
            .setSeekForwardIncrementMs(10_000)
            .build()
            .also { exo ->
                playerView.player = exo
                exo.addListener(listener)
                if (startPositionMs != C.TIME_UNSET && startPositionMs > 0) {
                    exo.setMediaItem(mediaItem, startPositionMs)
                } else {
                    exo.setMediaItem(mediaItem)
                }
                exo.playWhenReady = playWhenReady
                exo.prepare()
            }
    }

    private fun releasePlayer() {
        val exo = player ?: return
        startPositionMs = exo.currentPosition
        playWhenReady = exo.playWhenReady
        saveProgress(exo)
        exo.removeListener(listener)
        exo.release()
        player = null
        playerView.player = null
    }

    private fun saveProgress(exo: Player) {
        val id = movieId ?: return
        val duration = exo.duration
        if (exo.playbackState == Player.STATE_ENDED) {
            library.clearProgress(id)
        } else if (duration != C.TIME_UNSET && duration > 0) {
            library.saveProgress(id, exo.currentPosition, duration)
        }
    }

    private val listener = object : Player.Listener {
        override fun onPlaybackStateChanged(playbackState: Int) {
            if (playbackState == Player.STATE_ENDED) {
                movieId?.let(library::clearProgress)
                finish()
            }
        }

        override fun onPlayerError(error: PlaybackException) {
            Toast.makeText(this@PlayerActivity, "Playback error: ${error.errorCodeName}", Toast.LENGTH_LONG).show()
        }
    }

    private fun hideSystemBars() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    companion object {
        private const val EXTRA_URL = "url"
        private const val EXTRA_TITLE = "title"
        private const val EXTRA_MOVIE_ID = "movie_id"
        private const val EXTRA_FROM_START = "from_start"
        private const val STATE_POSITION = "position"
        private const val STATE_PLAY_WHEN_READY = "play_when_ready"

        fun play(context: Context, movie: Movie, fromStart: Boolean = false) {
            context.startActivity(
                Intent(context, PlayerActivity::class.java)
                    .putExtra(EXTRA_URL, movie.streamUrl)
                    .putExtra(EXTRA_TITLE, movie.title)
                    .putExtra(EXTRA_MOVIE_ID, movie.id)
                    .putExtra(EXTRA_FROM_START, fromStart),
            )
        }

        /** Plays an arbitrary URL without tracking resume progress. */
        fun playUrl(context: Context, url: String) {
            context.startActivity(
                Intent(context, PlayerActivity::class.java)
                    .putExtra(EXTRA_URL, url)
                    .putExtra(EXTRA_TITLE, url.substringAfterLast('/')),
            )
        }
    }
}
