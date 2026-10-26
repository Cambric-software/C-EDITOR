import 'package:flutter/material.dart';
import 'package:cambric_design/cambric_design.dart';

class VideoScreen extends StatefulWidget {
  const VideoScreen({super.key});

  @override
  State<VideoScreen> createState() => _VideoScreenState();
}

class _VideoScreenState extends State<VideoScreen> {
  final List<String> _tracks = ['Track 1', 'Track 2'];

  void _addTrack() {
    setState(() => _tracks.add('Track ${_tracks.length + 1}'));
  }

  @override
  Widget build(BuildContext context) {
    return DsPage(
      title: 'Video',
      child: Column(
        children: [
          Expanded(
            flex: 2,
            child: Container(
              color: Colors.black,
              child: const Center(
                child: Icon(Icons.play_arrow, size: 64, color: Colors.white),
              ),
            ),
          ),
          Expanded(
            flex: 1,
            child: Row(
              children: [
                SizedBox(
                  width: 120,
                  child: ListView.builder(
                    itemCount: _tracks.length,
                    itemBuilder: (context, i) => ListTile(
                      title: Text(_tracks[i]),
                    ),
                  ),
                ),
                Expanded(
                  child: Container(
                    color: Colors.grey[300],
                    child: const Center(child: Text('Timeline')),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(8),
            child: ElevatedButton(onPressed: _addTrack, child: const Text('Add Track')),
          ),
        ],
      ),
    );
  }
}