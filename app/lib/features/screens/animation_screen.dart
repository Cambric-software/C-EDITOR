import 'package:flutter/material.dart';
import 'package:cambric_design/cambric_design.dart';

class AnimationScreen extends StatefulWidget {
  const AnimationScreen({super.key});

  @override
  State<AnimationScreen> createState() => _AnimationScreenState();
}

class _AnimationScreenState extends State<AnimationScreen> {
  int _frame = 0;

  @override
  Widget build(BuildContext context) {
    return DsPage(
      title: 'Animation',
      child: Column(
        children: [
          Expanded(
            child: Center(
              child: Text('Frame $_frame'),
            ),
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              IconButton(
                icon: const Icon(Icons.skip_previous),
                onPressed: () => setState(() => _frame = (_frame - 1).clamp(0, 99)),
              ),
              IconButton(
                icon: const Icon(Icons.skip_next),
                onPressed: () => setState(() => _frame = (_frame + 1).clamp(0, 99)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}