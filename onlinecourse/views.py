from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import generic
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
import logging

# Import ALL required models
from .models import Course, Enrollment, Question, Choice, Submission

# Logger
logger = logging.getLogger(__name__)


# ---------------- USER AUTH ---------------- #

def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)

    elif request.method == 'POST':
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']

        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.info("New user")

        if not user_exist:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']

        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)

    return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


# ---------------- HELPER ---------------- #

def check_if_enrolled(user, course):
    if user.id is not None:
        return Enrollment.objects.filter(user=user, course=course).exists()
    return False


# ---------------- COURSE VIEWS ---------------- #

class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]

        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)

        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    if not check_if_enrolled(user, course) and user.is_authenticated:
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(
        reverse('onlinecourse:course_details', args=(course.id,))
    )


# ---------------- EXAM LOGIC ---------------- #

# Extract selected answers
def extract_answers(request):
    submitted_answers = []
    for key in request.POST:
        if key.startswith('choice'):
            submitted_answers.append(int(request.POST[key]))
    return submitted_answers


# SUBMIT VIEW
def submit(request, course_id):
    user = request.user
    course = get_object_or_404(Course, pk=course_id)

    # Get enrollment
    enrollment = Enrollment.objects.get(user=user, course=course)

    # Create submission
    submission = Submission.objects.create(enrollment=enrollment)

    # Get selected choices
    selected_ids = extract_answers(request)

    # Add choices to submission
    for choice_id in selected_ids:
        choice = Choice.objects.get(pk=choice_id)
        submission.choices.add(choice)

    # Redirect to result page
    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
    )


# RESULT VIEW
def show_exam_result(request, course_id, submission_id):
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(Submission, pk=submission_id)

    choices = submission.choices.all()

    total_score = 0
    total_grade = 0

    for question in course.question_set.all():
        total_grade += question.grade

        selected_ids = []
        for choice in choices:
            if choice.question == question:
                selected_ids.append(choice.id)

        # Check correctness
        if question.is_get_score(selected_ids):
            total_score += question.grade

    context = {
        'course': course,
        'choices': choices,
        'total_score': total_score,
        'total_grade': total_grade,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
