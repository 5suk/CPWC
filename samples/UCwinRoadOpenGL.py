from OpenGL.GLUT import *
from OpenGL.GL import *

class OpenGLSamples:

    def __init__(self):
        pass

    def DrawQUADS(self, k):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glEnable(GL_COLOR_MATERIAL)
        glColor4f(1.0, 1.0, 0.0, 0.5)
        glBegin(GL_QUADS)
        Left = -1.0 * k
        Bottom = -1.0 * k
        Right = 1.0 * k
        Top = 1.0 * k
        glVertex3f(Left, Bottom, 0)
        glVertex3f(Right, Bottom, 0)
        glVertex3f(Right, Top, 0)
        glVertex3f(Left, Top, 0)
        glEnd()

    def DrawLine(self, x1, y1, x2, y2, width):
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        glLineWidth(width)
        glEnable(GL_COLOR_MATERIAL)
        glColor4f(1.0, 0.0, 0.0, 0.5)
        glBegin(GL_LINES)
        glVertex2d(x1, y1)
        glVertex2d(x2, y2)
        glEnd()

    def DrawBack(self, r, g, b, a):
        glClearColor(r, g, b, a)
        glClear(GL_COLOR_BUFFER_BIT)
        glClear(GL_DEPTH_BUFFER_BIT)
